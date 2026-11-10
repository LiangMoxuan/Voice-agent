"""Mock 业务接口（B 维护）。官方沙箱账号到手后只改 base_url 与鉴权，接口形态不变。"""
import hashlib

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/mock", tags=["mock"])

CUSTOMERS = {
    "C0001": {"customer_id": "C0001", "name": "张先生",
              "masked_phone": "138****2211", "member_expire": "2026-12-15"},
    "C0002": {"customer_id": "C0002", "name": "李女士",
              "masked_phone": "139****3344", "member_expire": "2027-01-20"},
}

ORDERS = {
    "C0001": {"order_id": "O-7788", "status": "已发货", "plan": "PLUS年卡"},
    "C0002": {"order_id": "O-9911", "status": "已完成", "plan": "PLUS季卡"},
}


def _ticket_id(customer_id):
    h = hashlib.md5(customer_id.encode("utf-8")).hexdigest()[:6]
    return "T-%d" % (int(h, 16) % 9000 + 1000)


@router.get("/customers/{cid}")
def get_customer(cid: str):
    if cid not in CUSTOMERS:
        raise HTTPException(404, "customer_not_found")
    return CUSTOMERS[cid]


@router.get("/orders/{cid}")
def get_order(cid: str):
    if cid not in ORDERS:
        raise HTTPException(404, "order_not_found")
    return ORDERS[cid]


class TicketIn(BaseModel):
    customer_id: str
    content: str = Field(min_length=2, max_length=200)
    plan: str = ""


@router.post("/tickets")
def create_ticket(inp: TicketIn):
    return {"ticket_id": _ticket_id(inp.customer_id),
            "customer_id": inp.customer_id,
            "status": "created"}


class WritebackIn(BaseModel):
    tool_call_id: str
    session_id: str
    result: dict


@router.post("/writeback")
def writeback(inp: WritebackIn):
    from server.tools.writeback import write_back
    return write_back(inp.session_id, inp.result, inp.tool_call_id)
