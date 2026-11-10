"""对话状态机与槽位定义（B 维护）。

Day5 把 step() 补完即可接入；states/slots/can_transition 已经是最终结构。
"""

STATES = {
    "INIT":             {"next": ["GREETING"]},
    "GREETING":         {"must_say": "您好，我是京东客服小智",
                         "next": ["IDENTITY_CONFIRM"]},
    "IDENTITY_CONFIRM": {"slot": "customer_identity",
                         "ask": "请问您是张先生本人吗？",
                         "next": ["REQUIREMENT", "FALLBACK", "HUMAN_TRANSFER"]},
    "REQUIREMENT":      {"slot": "customer_need",
                         "ask": "您之前办理的会员下月到期，想跟您确认一下处理意向，现在方便吗？",
                         "next": ["SOLUTION", "FALLBACK"]},
    "SOLUTION":         {"slot": "selected_plan",
                         "must_say": "年卡续费享9折，有效期12个月，到期前短信提醒（无隐藏条款）",
                         "next": ["CONFIRM", "FALLBACK", "HUMAN_TRANSFER"]},
    "CONFIRM":          {"slot": "customer_decision",
                         "ask": "那我就按这个方案帮您登记了，可以吗？",
                         "next": ["WRITEBACK"]},
    "WRITEBACK":        {"tool": "write_back", "next": ["COMPLETED"]},
    "COMPLETED":        {"must_say": "感谢您的时间，祝您生活愉快，再见", "next": []},
    "HUMAN_TRANSFER":   {"must_say": "为您转接人工客服", "next": ["COMPLETED"]},
    "FALLBACK":         {"ask": "抱歉没听清，您能再说一遍吗？", "next": []},
}

SLOT_SCHEMA = {
    "customer_identity": {"enum": ["confirmed", "denied", "unclear"], "required": True},
    "customer_need":     {"free_text": True, "required": True},
    "selected_plan":     {"enum": ["renew_9off", "decline", "defer"], "required": True},
    "customer_decision": {"enum": ["agree", "refuse", "need_think"], "required": True},
    "followup_required": {"bool": True, "required": True},
    "final_status":      {"enum": ["已登记工单", "拒绝-已记录原因", "错号", "转人工"],
                          "required": True},
}

MAX_TURNS_PER_STATE = 3
FAIL_TO_HUMAN = 3


def can_transition(cur, nxt):
    """非法跳转直接拒绝，防止模型乱跳。"""
    if cur == "FALLBACK":
        return True
    return nxt in STATES.get(cur, {}).get("next", [])


async def step(session, user_text):
    """TODO(B, Day5)：按 docs/design/fsm-draft-b.md 实现。

    实现顺序：
      1. 把 user_text 加进 session["history"]
      2. chat(build_state_messages(...), json_mode=True)
      3. parse_json_reply 拿到 slots_update / next_state / reply
      4. can_transition 校验，非法则留在原状态并记日志
      5. 更新 session 的 state/slots，写 turns 表
      6. 返回 reply
    """
    raise NotImplementedError("B 在 Day5 实现 fsm.step")
