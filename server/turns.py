"""协议消息 → 数据库落库（C 维护，Day3 主线）。

`/ws/control` 上流转的每条 JSON 消息都过这里：ASR 文本落成用户轮次，
流式增量攒成 Agent 轮次，时延打点、工具记录、回写结果各就各位。
协议字段一个不改（docs/protocol-v0.md 已冻结），只做记录。

不落库的消息类型：echo、raw、tts 的分句增量 —— 它们属于传输过程，
真正要留痕的是"用户说了什么"和"Agent 说了什么"。
"""
import logging

from server import db
from server.logs import log_event
from server.tools.writeback import write_back

log = logging.getLogger("turns")

ROLE_USER = "user"
ROLE_AGENT = "agent"


class Recorder:
    """一个进程内实例即可，状态随会话累积，进程重启后只丢未落库的流式缓冲。"""

    def __init__(self):
        self._state = {}   # session_id -> 当前 FSM 状态
        self._buf = {}     # (session_id, turn_id) -> [delta, delta, ...]

    def current_state(self, session_id):
        return self._state.get(session_id)

    def reset(self):
        self._state.clear()
        self._buf.clear()

    def handle(self, msg):
        """处理一条协议消息，返回 {ok, action, ...} 供调用方与测试断言。"""
        if not isinstance(msg, dict):
            return {"ok": False, "action": "ignored", "reason": "not_a_dict"}
        mtype = msg.get("type")
        sid = msg.get("session_id")
        if not mtype or not sid:
            return {"ok": False, "action": "ignored", "reason": "missing_type_or_session"}

        try:
            db.add_session(sid, msg.get("ts"))
            return getattr(self, "_on_" + mtype, self._on_unknown)(msg, sid)
        except Exception as e:  # 落库失败不能把整条信道带崩
            log.exception("消息落库失败 type=%s session=%s", mtype, sid)
            log_event("record_error", session_id=sid, msg_type=mtype, error=str(e))
            return {"ok": False, "action": "error", "reason": str(e)}

    # ---- 各类消息 ----

    def _on_asr_final(self, msg, sid):
        text = (msg.get("text") or "").strip()
        if not text:
            return {"ok": False, "action": "ignored", "reason": "empty_text"}
        row_id = db.add_turn(sid, ROLE_USER, text,
                             state=self.current_state(sid), ts=msg.get("ts"))
        log_event("turn", session_id=sid, role=ROLE_USER, turn_id=msg.get("turn_id"),
                  text=text, row_id=row_id)
        return {"ok": True, "action": "turn_user", "row_id": row_id}

    def _on_agent_text_delta(self, msg, sid):
        delta = msg.get("delta") or ""
        if not delta:
            return {"ok": False, "action": "ignored", "reason": "empty_delta"}
        self._buf.setdefault((sid, msg.get("turn_id")), []).append(delta)
        return {"ok": True, "action": "buffer_agent", "buffered": len(self._buf[(sid, msg.get("turn_id"))])}

    def _on_tts_segment(self, msg, sid):
        # final=true 表示本轮这句说完了，把攒下的文字收成一行
        if not msg.get("final"):
            return {"ok": True, "action": "tts_segment_noop"}
        return self._flush_agent(sid, msg.get("turn_id"))

    def _on_state_change(self, msg, sid):
        to = msg.get("to")
        # 先把上一状态下说出口的话收口（带着旧状态入库），再切状态，
        # 否则这一轮会被记到新状态上，评测归因时就找不到是哪一步出的话。
        flushed = self._flush_agent(sid, None)
        self._state[sid] = to
        log_event("state", session_id=sid, from_state=msg.get("from"), to_state=to)
        return {"ok": True, "action": "state_change", "to": to,
                "flushed": flushed.get("row_id")}

    def _on_interrupt(self, msg, sid):
        # 被打断也要留痕：已经说出口的半句话同样要能复盘
        flushed = self._flush_agent(sid, msg.get("turn_id"))
        log_event("interrupt", session_id=sid, turn_id=msg.get("turn_id"),
                  reason=msg.get("reason"))
        return {"ok": True, "action": "interrupt", "flushed": flushed.get("row_id")}

    def _on_latency_mark(self, msg, sid):
        db.add_latency(sid, msg.get("turn_id"), msg.get("marks"))
        log_event("latency", session_id=sid, turn_id=msg.get("turn_id"),
                  marks=msg.get("marks"))
        return {"ok": True, "action": "latency"}

    def _on_tool_log(self, msg, sid):
        db.add_tool_log(sid, msg.get("tool"), msg.get("args"), msg.get("result"),
                        msg.get("latency_ms"), msg.get("tool_call_id"),
                        msg.get("turn_id"))
        log_event("tool", session_id=sid, tool=msg.get("tool"),
                  tool_call_id=msg.get("tool_call_id"),
                  latency_ms=msg.get("latency_ms"))
        return {"ok": True, "action": "tool_log"}

    def _on_writeback(self, msg, sid):
        r = write_back(sid, msg.get("payload") or {}, msg.get("tool_call_id"))
        if r.get("inserted"):
            db.set_final_status(sid, (msg.get("payload") or {}).get("final_status"),
                                msg.get("ts"))
        log_event("writeback", session_id=sid, tool_call_id=msg.get("tool_call_id"),
                  result=r)
        return {"ok": True, "action": "writeback", "inserted": r.get("inserted")}

    def _on_unknown(self, msg, sid):
        return {"ok": True, "action": "ignored", "reason": "unknown_type:%s" % msg.get("type")}

    # ---- 内部 ----

    def _flush_agent(self, sid, turn_id):
        """把 (sid, turn_id) 或该会话所有缓冲收成一行 Agent 轮次。"""
        keys = [(sid, turn_id)] if turn_id is not None else \
            [k for k in self._buf if k[0] == sid]
        row_id = None
        for k in keys:
            parts = self._buf.pop(k, None)
            if not parts:
                continue
            text = "".join(parts).strip()
            if not text:
                continue
            row_id = db.add_turn(sid, ROLE_AGENT, text, state=self.current_state(sid))
            log_event("turn", session_id=sid, role=ROLE_AGENT,
                      turn_id=k[1], text=text, row_id=row_id)
        return {"ok": True, "action": "turn_agent", "row_id": row_id}


recorder = Recorder()
