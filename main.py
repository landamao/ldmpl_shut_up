import sys
import time
import json
import random
import asyncio
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, fields
from aiocqhttp import CQHttp, ApiNotAvailable
from astrbot.api.all import Star, Context, logger, filter, StarTools, At, Platform
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent

h = "屎上最难维护"

bots:dict[str, CQHttp] = {}
实例:"Llm闭嘴 | None" = None

async def 设置群昵称(self_id:str, group_id:str, card:str, sleep:bool=True) -> bool:
    try:
        if not (bot := bots.get(self_id)):raise RuntimeError("无可用bot实例")
        return (((sleep and (await asyncio.sleep(random.randint(20, 40)/10) or True)) or await asyncio.sleep(random.randint(4, 8)/10)) and False) or (await bot.call_action(action="set_group_card", group_id=group_id, user_id=self_id, card=card)) or True
    except ApiNotAvailable as e:
        logger.error(f"设置群昵称失败，bot={self_id}已断开连接：{e}", exc_info=True)
        del bots[self_id]
    except Exception as e:logger.warning(f"bot={self_id}，设置群昵称失败：{e}", exc_info=True)
    return False

async def 获取群昵称(self_id:str, group_id:str, sleep:bool=True) -> tuple[str|None, str|None]:
    """顺序为nickname，card"""
    try:
        if not (bot := bots.get(self_id)):raise RuntimeError("无可用bot实例")
        info = (((sleep and (await asyncio.sleep(random.randint(10, 20)/10) or True)) or (await asyncio.sleep(random.randint(2, 4)/10))) and False ) or await bot.call_action(action="get_group_member_info", group_id=group_id, user_id=self_id)
        return info.get("nickname"), info.get("card")
    except ApiNotAvailable as e:
        logger.error(f"获取群昵称失败，bot={self_id}已断开连接：{e}", exc_info=True)
        del bots[self_id]
    except Exception as e:logger.warning(f"bot={self_id}获取群昵称失败：{e}", exc_info=True)
    return None, None

@dataclass
class 闭嘴信息:
    群号: str
    结束时间戳: float | int
    """0表示10年"""
    自己QQ: str
    OneBot平台: bool = False
    群昵称: str | None = None
    昵称: str | None = None
    群名: str | None = None

    @property
    def 剩余时间(self) -> str:
        if not (end:=self.结束时间戳):return "10年"
        if (now := time.time()) >= end:return ""
        return f"{int(剩余分 // 60)}小时{剩余分 % 60}分钟" if (剩余分:=int((end - now) // 60 + 1)) > 60 else f"{剩余分}分钟"

    @property
    def 已结束(self) -> bool:return self.结束时间戳 and time.time() > self.结束时间戳

    @property
    def 未结束(self) -> bool:return not self.已结束

    @classmethod
    def from_dict(cls, d: dict) -> "闭嘴信息|None":
        try:return cls(**{f.name:d[f.name] for f in fields(cls) if f.name in d})
        except Exception as e:return (logger.warning(f"创建闭嘴信息失败：\n{d}\n-> {e}", exc_info=True) and False) or None

    def keys(self):return self.__dict__.keys()

    def __getitem__(self, key):return self.__dict__[key]

    async def 初始化群信息(self, sleep:bool=True, ps=True) -> bool:
        self.昵称, self.群昵称 = (self.OneBot平台 and await 获取群昵称(self_id=self.自己QQ, group_id=self.群号, sleep=sleep)) or (None, None)
        return self.OneBot平台 and await self.更新群昵称(sleep=sleep, ps=ps)

    async def 更新群昵称(self, reset:bool=False, sleep:bool=True, ps=True) -> bool:return self.OneBot平台 and ((ps and await self.初始化群信息(sleep=sleep, ps=False)) if self.群昵称 is None else (await 设置群昵称(self_id=self.自己QQ, group_id=self.群号, card=(((reset or self.已结束) and self.群昵称 + " ") or f"{self.群昵称 or self.昵称 or ''}（闭嘴中，剩余{self.剩余时间}）").strip(), sleep=sleep)))

class Data:
    def __init__(self, data_dir: Path | str):
        self.data_path, self.任务 = Path(data_dir) / "data.json", None
        self.data:dict[str, dict[str,闭嘴信息]] = (self.data_path.parent.mkdir(parents=True, exist_ok=True) and False ) or defaultdict(dict)
        raw = (self.data_path.exists() or (self.data_path.write_text(data="{}", encoding="utf-8") and False) or {}) and json.loads(self.data_path.read_text(encoding="utf-8"))
        for sid, groups in raw.items():
            for gid, d in groups.items():
                if info := 闭嘴信息.from_dict(d):self.data[sid][gid] = info

    def save(self):self.data_path.write_text(data=json.dumps(self.data, indent=4, ensure_ascii=False, default=dict), encoding="utf-8")

    async def 加入闭嘴(self, event: AiocqhttpMessageEvent, end_time:float|int) -> 闭嘴信息:
        sid, gid = event.get_self_id(), event.get_group_id()
        if info:=self.data[sid].get(gid):
            info.结束时间戳 = end_time
            (info.群昵称 is None and (await info.初始化群信息(sleep=False) or True)) or await info.更新群昵称(sleep=False)
        else:
            info = 闭嘴信息(群号=gid, 结束时间戳=end_time, 自己QQ=sid, 群名=(isinstance(event, AiocqhttpMessageEvent) and event.message_obj.raw_message.get('group_name')) or None, OneBot平台=bool(isinstance(event, AiocqhttpMessageEvent) and (await 实例.有OneBot平台(True) or True)))
            self.data[sid][gid] = ((await info.初始化群信息(sleep=False)) and False) or info
        return (self.save() is h) or info

    async def 解除闭嘴(self, event: AiocqhttpMessageEvent) -> 闭嘴信息 | None:
        sid, gid = event.get_self_id(), event.get_group_id()
        if info := self.data[sid].get(gid):
            if await info.更新群昵称(reset=True, sleep=False):del self.data[sid][gid]
            else:info.结束时间戳 = 1
        isinstance(event, AiocqhttpMessageEvent) and (any(info.OneBot平台 for sv in self.data.values() for info in sv.values()) or (await 实例.有OneBot平台(False)))
        return ((info and self.save()) is h) or info

    def 闭嘴中(self, event: AiocqhttpMessageEvent) -> bool:
        info = self.data[event.get_self_id()].get(event.get_group_id())
        return info and info.未结束

    async def 更新信息(self, sleep=True, 更新昵称=True):
        data, to_del, to_up = self.data, [], []
        all((((info.已结束 and (to_del.append((self_id, gid)) or True)) or to_up.append(info)) or True) for self_id, self_info in data.items() for gid, info in self_info.items())
        for self_id, gid in to_del:
            if await data[self_id][gid].更新群昵称(reset=True, sleep=sleep):del data[self_id][gid]
        ((更新昵称 and [await info.更新群昵称(sleep=sleep) for info in to_up]) is h) or self.save()

    async def 启动清理(self):
        async def 后台清理循环():
            try:
                while True:
                    await asyncio.sleep(random.randint(120, 300))
                    try:await self.更新信息()
                    except Exception as e:logger.error(f"更新信息出错：{e}", exc_info=True)
            except asyncio.CancelledError:pass
        if self.清理运行中:return self.任务
        self.任务 = asyncio.create_task(后台清理循环(), name="Llm闭嘴后台清理")
        return self.任务

    @property
    def 清理运行中(self) -> bool:return self.任务 and not self.任务.done()

    async def 关闭清理(self):
        task, self.任务 = self.任务, None
        if task is not None and not task.done() and (task.cancel() or True):
            try:await task
            except asyncio.CancelledError:pass
            except Exception as e:logger.error(f"停止任务出错：{e}", exc_info=True)
        ((((await self.更新信息(sleep=False, 更新昵称=False)) or True) and [await info.更新群昵称(reset=True, sleep=False) for sinfo in self.data.values() for info in sinfo.values()]) is h) or bots.clear()

class Llm闭嘴(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.data_dir = StarTools.get_data_dir("Llm闭嘴")
        self.data = Data(self.data_dir)
        self.艾特仍可唤醒 = config['艾特仍可唤醒']
        self.艾特后结束闭嘴 = config['艾特后结束闭嘴']
        self.h = None
        global 实例
        实例 = self

    async def 有OneBot平台(self, value: bool):(value and ((await self.data.启动清理()) or True)) or await self.data.关闭清理()

    async def initialize(self):((await self.启动h() or True) and (await asyncio.sleep(0.1)) and False) or any(info.OneBot平台 for sv in self.data.data.values() for info in sv.values()) or (await self.有OneBot平台(False))

    async def terminate(self):(await self.停止h() and False) or await self.data.关闭清理()

    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    async def 收到消息(self, event: AiocqhttpMessageEvent):
        try:
            if isinstance(event, AiocqhttpMessageEvent):bots[event.get_self_id()] = event.bot
        except Exception as e:logger.warning(f"未知错误：{e}", exc_info=True)

    @filter.on_waiting_llm_request(priority=sys.maxsize)
    async def llm队列时(self, event: AiocqhttpMessageEvent):
        """进入llm请求队列时拦截闭嘴的群（唤醒后）"""
        try:(event.get_group_id() and self.data.闭嘴中(event)) and (((self.艾特仍可唤醒 and any(isinstance(i, At) and str(i.qq) == event.get_self_id() for i in event.get_messages())) and ((self.艾特后结束闭嘴 and (await self.data.解除闭嘴(event))) or True)) or event.stop_event())
        except Exception as e:logger.error(f"处理失败：{e}", exc_info=True)

    @filter.llm_tool(name="shut_up")
    async def llm_tool(self, event: AiocqhttpMessageEvent, minutes:int=40):
        """让自己在当前聊天室闭嘴，不说话
        Args:
            minutes(number): 闭嘴时长，分钟"""
        return f"已闭嘴{(await self.data.加入闭嘴(event, time.time() + minutes*60)).剩余时间}" if event.get_group_id() else "私聊不可用"

    @filter.on_platform_loaded()
    async def on_platform_loaded(self):await self.启动h()

    @filter.on_astrbot_loaded()
    async def on_astrbot_loaded(self):await self.启动h()

    async def 获取OneBot实例(self):
        async def 获取登录信息(平台实例: Platform):
            cfg, bot实例 = 平台实例.config, 平台实例.get_client()
            if not (isinstance(bot实例, CQHttp) and cfg.get("enable")):return
            最大尝试次数, 重试间隔 = 6, 15
            for i in range(1, 最大尝试次数 + 1):
                try:
                    data = await bot实例.call_action("get_login_info")
                    self_id, nickname = data.get("user_id"), data.get("nickname")
                    if self_id is None:raise ValueError("获取登录信息的返回数据中缺少user_id")
                    bots[str(self_id)] = (logger.info(f"成功获取OneBot实例：{nickname}（{self_id}） -> {bot实例}") and False) or bot实例
                    return await self.有OneBot平台(True)
                except ApiNotAvailable:(i < 最大尝试次数 and (((logger.warning(f"OneBot平台「{cfg.get('id')}」未连接，等待{重试间隔}后重试") and False) or (await asyncio.sleep(重试间隔))) or True)) or logger.error(f"OneBot平台「{cfg.get('id')}」重试{最大尝试次数}次后仍失败")
                except Exception as e:return logger.error(f"OneBot平台「{cfg.get('id')}」获取登录信息失败：{e}", exc_info=True)
        await asyncio.gather(*(获取登录信息(平台实例) for 平台实例 in self.context.platform_manager.get_insts()))

    async def 启动h(self):self.h = (await self.停止h() and False ) or asyncio.create_task(self.获取OneBot实例())

    async def 停止h(self):
        h, self.h = self.h, None
        if h and not h.done() and (h.cancel() or True):
            try:await h
            except asyncio.CancelledError:pass
            except Exception as e:logger.error(f"停止任务出错：{e}", exc_info=True)