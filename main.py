import sys
import time
import json
import random
import asyncio
from pathlib import Path
from aiocqhttp import CQHttp
from dataclasses import dataclass
from collections import defaultdict
from astrbot.api.all import Star, Context, logger, AstrBotConfig, filter, StarTools
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent

bots:dict[str, CQHttp] = {}

async def 设置群昵称(self_id:str, group_id:str, card:str, sleep:bool=True) -> bool:
    try:
        if not (bot := bots.get(self_id)):
            raise RuntimeError("无可用event实例")
        if sleep:
            await asyncio.sleep(random.randint(2, 4))
        else:
            await asyncio.sleep(random.randint(4, 8)/10)
        await bot.call_action(
            action="set_group_card",
            group_id=group_id,
            user_id=self_id,
            card=card
        )
        return True
    except Exception as e:
        logger.warning(f"设置群昵称失败：{e}", exc_info=True)
        return False

async def 获取群昵称(self_id:str, group_id:str, sleep:bool=True) -> tuple[str, str] | None:
    """顺序为nickname，card"""
    try:
        if not (bot := bots.get(self_id)):
            raise RuntimeError("无可用event实例")
        if sleep:
            await asyncio.sleep(random.randint(1, 5))
        info = await bot.call_action(
            action="get_group_member_info",
            group_id=group_id,
            user_id=self_id
        )
        return info.get("nickname"), info.get("card")
    except Exception as e:
        logger.warning(f"获取群昵称失败：{e}", exc_info=True)
        return None

@dataclass
class 闭嘴信息:
    群号: str
    结束时间戳: float | int
    """0表示10年"""
    自己QQ: str
    群昵称: str | None = None
    昵称: str | None = None
    群名: str | None = None

    @property
    def 剩余时间(self) -> str:
        now = time.time()
        end = self.结束时间戳
        if not end:
            return "10年"
        if now >= end:
            return ""
        剩余秒 = end - now
        剩余分 = int(剩余秒 // 60 + 1) # 向上取整
        if 剩余分 < 60:
            return f"{剩余分}分钟"
        剩余时 = int(剩余分 // 60)
        剩余分 %= 60
        return f"{剩余时}小时{剩余分}分钟"

    @property
    def 已结束(self) -> bool:
        return time.time() > self.结束时间戳 if self.结束时间戳 else False

    @property
    def 未结束(self) -> bool:
        return not self.已结束

    def to_dict(self) -> dict:
        return {
            "群号":self.群号,
            "结束时间戳":self.结束时间戳,
            "自己QQ":self.自己QQ,
            "群昵称":self.群昵称,
            "昵称":self.昵称,
            "群名":self.群名
        }

    @classmethod
    def from_dict(cls, data: dict) -> "闭嘴信息 | None":
        try:
            return cls(**data)
        except Exception:
            return None

    def keys(self):
        return self.to_dict().keys()

    def __getitem__(self, key):
        return getattr(self, key)

    async def 初始化群信息(self, sleep:bool=True, ps=False) -> bool:
        r = await 获取群昵称(self_id=self.自己QQ, group_id=self.群号, sleep=sleep)
        if r:
            self.昵称, self.群昵称 = r
        return await self.更新群昵称(sleep=sleep, ps=ps)

    async def 更新群昵称(self, reset:bool=False, sleep:bool=True, ps=False) -> bool:
        if self.群昵称 is None:
            if ps:
                return False
            return await self.初始化群信息(sleep=sleep, ps=True)
        if reset or self.已结束:
            card = self.群昵称
        else:
            card = f"{self.群昵称 or self.昵称 or ''}（闭嘴中，剩余{self.剩余时间}）"
        return await 设置群昵称(self_id=self.自己QQ, group_id=self.群号, card=card, sleep=sleep)

class Data:
    def __init__(self, data_dir: Path | str):
        self.data_dir = Path(data_dir)
        self.data_path = self.data_dir / "data.json"
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self.data:dict[str, dict[str,闭嘴信息]] = defaultdict(dict)
        self.任务 = None
        self.load()

    def load(self):
        if not self.data_path.exists():
            self.data_path.write_text(data="{}", encoding="utf-8")
            return
        raw = json.loads(self.data_path.read_text(encoding="utf-8"))
        for sid, groups in raw.items():
            for gid, d in groups.items():
                info = 闭嘴信息.from_dict(d)
                if info:
                    self.data[sid][gid] = info

    def save(self):
        self.data_path.write_text(
            data=json.dumps(self.data, indent=4, ensure_ascii=False, default=dict), # type: ignore
            encoding="utf-8"
        )

    async def 加入闭嘴(self, event: AiocqhttpMessageEvent, end_time:float|int) -> 闭嘴信息:
        sid = event.get_self_id()
        gid = event.get_group_id()
        gna = event.message_obj.raw_message.get('group_name')
        info = self.data[sid].get(gid)
        if info is None:
            info = 闭嘴信息(群号=gid, 结束时间戳=end_time, 自己QQ=sid, 群名=gna)
            self.data[sid][gid] = info
            await info.初始化群信息(sleep=False)
        else:
            info.结束时间戳 = end_time
            if info.群昵称 is None:
                await info.初始化群信息(sleep=False)
            else:
                await info.更新群昵称(sleep=False)
        self.save()
        return self.data[sid][gid]

    async def 解除闭嘴(self, event: AiocqhttpMessageEvent) -> 闭嘴信息 | None:
        sid = event.get_self_id()
        gid = event.get_group_id()
        if gid in self.data[sid]:
            info = self.data[sid][gid]
            if await info.更新群昵称(reset=True, sleep=False):
                del self.data[sid][gid]
            else:
                info.结束时间戳 = 1
            self.save()
            return info
        return None

    def 闭嘴中(self, event: AiocqhttpMessageEvent) -> bool:
        info = self.data[event.get_self_id()].get(event.get_group_id())
        return info and info.未结束

    async def 更新信息(self, sleep=True, 更新昵称=True):
        data = self.data
        to_del = []
        to_up = []
        for self_id, self_info in data.items():
            for gid, info in self_info.items():
                if info.已结束:
                    to_del.append((self_id, gid))
                else:
                    to_up.append(info)
        for self_id, gid in to_del:
            if await data[self_id][gid].更新群昵称(reset=True, sleep=sleep):
                del data[self_id][gid]

        if 更新昵称:
            for info in to_up:
                await info.更新群昵称(sleep=sleep)
        self.save()

    async def 启动清理(self):
        """启动后台周期清理任务。"""
        async def 后台清理循环():
            try:
                while True:
                    await asyncio.sleep(random.randint(120, 300))
                    try:
                        await self.更新信息()
                    except Exception as e:
                        logger.error(f"更新信息出错：{e}", exc_info=True)
            except asyncio.CancelledError:
                pass
        if self.清理运行中:
            return self.任务
        self.任务 = asyncio.create_task(后台清理循环(), name="Llm闭嘴后台清理")
        return self.任务

    @property
    def 清理运行中(self) -> bool:
        """判断后台清理任务是否正在运行"""
        task = self.任务
        return task is not None and not task.done()

    async def 关闭清理(self):
        """停止运行中的后台清理任务，重置群昵称"""
        task, self.任务 = self.任务, None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"停止任务出错：{e}", exc_info=True)
        await self.更新信息(sleep=False, 更新昵称=False)
        for sinfo in self.data.values():
            for info in sinfo.values():
                await info.更新群昵称(reset=True, sleep=False)
        bots.clear()

class Llm闭嘴(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.data_dir = StarTools.get_data_dir("Llm闭嘴")
        self.data = Data(self.data_dir)
        self.config = config
        self.config['懒大猫牛逼'] = "懒大猫实际上太牛逼了"
        self.config.save_config()
        self.h = None

    async def initialize(self) -> None:
        await self.启动h()
        await self.data.启动清理()

    async def terminate(self) -> None:
        await self.停止h()
        await self.data.关闭清理()

    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    async def 收到消息(self, event: AiocqhttpMessageEvent):
        try:
            if not isinstance(event, AiocqhttpMessageEvent):
                return
            bots[event.get_self_id()] = event.bot
        except Exception as e:
            logger.warning(f"未知错误：{e}", exc_info=True)

    @filter.on_waiting_llm_request(priority=sys.maxsize)
    async def llm队列时(self, event: AiocqhttpMessageEvent):
        """进入llm请求队列时拦截闭嘴的群（唤醒后）"""
        try:
            if not isinstance(event, AiocqhttpMessageEvent):
                return
            if not event.get_group_id():
                return
            if self.data.闭嘴中(event):
                event.stop_event()
        except Exception as e:
            logger.error(f"处理失败：{e}", exc_info=True)

    @filter.llm_tool(name="shut_up")
    async def llm_tool(self, event: AiocqhttpMessageEvent, minutes:int=40):
        """让自己在当前聊天室闭嘴，不说话
        Args:
            minutes(number): 闭嘴时长，分钟"""
        if not isinstance(event, AiocqhttpMessageEvent):
            return "当前平台不可用"
        if not event.get_group_id():
            return "私聊不可用"
        end_time = time.time() + minutes*60
        info = await self.data.加入闭嘴(event, end_time)
        return f"已闭嘴{info.剩余时间}"

    @filter.on_platform_loaded()
    async def on_platform_loaded(self):
        await self.启动h()

    @filter.on_astrbot_loaded()
    async def on_astrbot_loaded(self):
        await self.启动h()

    async def 获取OneBot实例(self):
        平台管理器 = getattr(self.context, "platform_manager", None)
        if not 平台管理器:
            logger.warning("获取平台管理器（platform_manager）失败")
            return

        获取实例列表 = getattr(平台管理器, "get_insts", None)
        if not callable(获取实例列表):
            logger.warning("平台管理器（platform_manager）没有 获取实例列表（get_insts）方法")
            return

        平台实例列表 = 获取实例列表()
        if not 平台实例列表:
            logger.warning("未发现任何平台实例")
            return

        候选实例列表 = []
        for 平台实例 in 平台实例列表: # type: ignore
            bot实例 = None
            获取实例 = getattr(平台实例, "get_client", None)
            if callable(获取实例):
                bot实例 = 获取实例()
            if not bot实例:
                bot实例 = getattr(平台实例, "bot", None)
            if not bot实例:
                bot实例 = getattr(平台实例, "client", None)

            if bot实例 and hasattr(bot实例, "call_action") and isinstance(bot实例, CQHttp):
                logger.info(f"找到OneBot实例: {type(bot实例).__name__}")
                候选实例列表.append(bot实例)

        if not 候选实例列表:
            logger.warning("未找到任何候选OneBot实例")
            return
        async def 获取登录信息(bot实例):

            最大尝试次数 = 6
            重试间隔 = 15

            for i in range(1, 最大尝试次数 + 1):
                try:
                    data = await bot实例.call_action("get_login_info")
                    self_id = data.get("user_id")
                    nickname = data.get("nickname")
                    if self_id is None:
                        raise ValueError("返回数据中缺少 user_id")
                    logger.info(f"成功获取OneBot实例：{nickname}（{self_id}） -> {bot实例}")
                    bots[str(self_id)] = bot实例
                    return
                except Exception as e:
                    if i < 最大尝试次数:
                        logger.warning(
                            f"平台 {type(bot实例).__name__} 获取登录信息失败（尝试 {i}/{最大尝试次数}）: {e}，"
                            f"{重试间隔} 秒后重试..."
                        )
                        await asyncio.sleep(重试间隔)
                    else:
                        logger.error(f"平台 {type(bot实例).__name__} 重试 {最大尝试次数} 次后仍失败")

        tasks = [获取登录信息(实例) for 实例 in 候选实例列表]
        await asyncio.gather(*tasks)

    async def 启动h(self):
        await self.停止h()
        self.h = asyncio.create_task(self.获取OneBot实例())

    async def 停止h(self):
        h = self.h
        if h and not h.done():
            h.cancel()
            try:
                await h
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"停止任务出错：{e}", exc_info=True)