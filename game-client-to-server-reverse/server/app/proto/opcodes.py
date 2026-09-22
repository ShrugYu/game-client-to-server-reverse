"""app.proto.opcodes —— 消息号表

这里是"反推出来的协议地图"的落点。
从 dump.cs 的 switch(msgId) / Lua 的 cmd 常量 / UE 的 packet id 提取后填这里。
命名约定：<模块>_<方向>，REQ=客户端上行，RES=服务端下行，NTF=服务端推送。
"""
from __future__ import annotations

from enum import IntEnum


class OP(IntEnum):
    # ---- 连接 / 握手 ----
    HANDSHAKE_REQ = 0x0001
    HANDSHAKE_RES = 0x0002
    HEARTBEAT_REQ = 0x0003
    HEARTBEAT_RES = 0x0004
    KICK_NTF      = 0x0005

    # ---- 账号 ----
    LOGIN_REQ     = 0x0101
    LOGIN_RES     = 0x0102
    REGISTER_REQ  = 0x0103
    REGISTER_RES  = 0x0104

    # ---- 角色 ----
    CHAR_LIST_REQ = 0x0201
    CHAR_LIST_RES = 0x0202
    CHAR_CREATE_REQ = 0x0203
    CHAR_CREATE_RES = 0x0204
    CHAR_SELECT_REQ = 0x0205
    CHAR_SELECT_RES = 0x0206
    CHAR_DELETE_REQ = 0x0207

    # ---- 场景 / 进入游戏 ----
    ENTER_SCENE_REQ = 0x0301
    ENTER_SCENE_RES = 0x0302
    MOVE_REQ      = 0x0303
    MOVE_NTF      = 0x0304
    PLAYER_INFO_NTF = 0x0305

    # ---- 邮件 ----
    MAIL_LIST_REQ   = 0x0401
    MAIL_LIST_RES   = 0x0402
    MAIL_READ_REQ   = 0x0403
    MAIL_READ_RES   = 0x0404
    MAIL_CLAIM_REQ  = 0x0405
    MAIL_CLAIM_RES  = 0x0406
    MAIL_NEW_NTF    = 0x0407
    MAIL_DELETE_REQ = 0x0408

    # ---- 充值 / 支付 ----
    PAY_PRODUCT_LIST_REQ = 0x0501
    PAY_PRODUCT_LIST_RES = 0x0502
    PAY_REQ              = 0x0503
    PAY_RES              = 0x0504

    # ---- 房间 / 匹配 ----
    ROOM_CREATE_REQ = 0x0601
    ROOM_CREATE_RES = 0x0602
    ROOM_JOIN_REQ   = 0x0603
    ROOM_JOIN_RES   = 0x0604
    ROOM_LEAVE_REQ  = 0x0605
    ROOM_LEAVE_RES  = 0x0606
    ROOM_READY_REQ  = 0x0607
    ROOM_READY_RES  = 0x0608
    ROOM_START_REQ  = 0x0609
    ROOM_START_RES  = 0x060A
    ROOM_INFO_NTF   = 0x060B

    # ---- 战斗 ----
    BATTLE_ACTION_REQ = 0x0701
    BATTLE_ACTION_RES = 0x0702
    BATTLE_STATE_NTF  = 0x0703
    BATTLE_RESULT_NTF = 0x0704

    # ---- 掉落 / 物资 ----
    DROP_TEST_REQ = 0x0801
    DROP_TEST_RES = 0x0802
    DROP_NTF      = 0x0803
    BAG_LIST_REQ  = 0x0804
    BAG_LIST_RES  = 0x0805

    # ---- 系统 ----
    ERROR_NTF     = 0x7F01


# 错误码
class ERR:
    OK = 0
    BAD_PACKET = 1
    BAD_VERSION = 2
    NEED_LOGIN = 3
    AUTH_FAILED = 4
    ACCOUNT_EXISTS = 5
    NO_CHAR = 6
    CHAR_LIMIT = 7
    RATE_LIMITED = 8
    MAIL_NOT_FOUND = 9
    MAIL_ALREADY_CLAIMED = 10
    MAIL_BAG_FULL = 11
    PAY_PRODUCT_NOT_FOUND = 12
    PAY_FAILED = 13
    ROOM_NOT_FOUND = 14
    ROOM_FULL = 15
    ROOM_NOT_OWNER = 16
    ROOM_NOT_READY = 17
    ALREADY_IN_ROOM = 18
    BATTLE_NOT_ACTIVE = 19
    BAG_FULL = 20
    INTERNAL = 99


ERR_TEXT = {
    ERR.OK: "ok",
    ERR.BAD_PACKET: "malformed packet",
    ERR.BAD_VERSION: "client version mismatch",
    ERR.NEED_LOGIN: "please login first",
    ERR.AUTH_FAILED: "invalid account or password",
    ERR.ACCOUNT_EXISTS: "account already exists",
    ERR.NO_CHAR: "character not found",
    ERR.CHAR_LIMIT: "character limit reached",
    ERR.RATE_LIMITED: "too many attempts",
    ERR.MAIL_NOT_FOUND: "mail not found",
    ERR.MAIL_ALREADY_CLAIMED: "reward already claimed",
    ERR.MAIL_BAG_FULL: "bag is full",
    ERR.PAY_PRODUCT_NOT_FOUND: "product not found",
    ERR.PAY_FAILED: "payment failed",
    ERR.ROOM_NOT_FOUND: "room not found",
    ERR.ROOM_FULL: "room is full",
    ERR.ROOM_NOT_OWNER: "only owner can start",
    ERR.ROOM_NOT_READY: "some members not ready",
    ERR.ALREADY_IN_ROOM: "already in a room",
    ERR.BATTLE_NOT_ACTIVE: "battle not active",
    ERR.BAG_FULL: "bag is full",
    ERR.INTERNAL: "internal error",
}