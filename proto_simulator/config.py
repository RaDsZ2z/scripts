# -*- coding: utf-8 -*-
"""
proto_simulator 配置文件

路径常量、协议枚举、包头参数等
"""

import os
from pathlib import Path

# ── 路径 ──────────────────────────────────────────────
# 项目根目录（proto_simulator/ 上两级 → garden_client/）
PROJ_ROOT = Path(__file__).resolve().parent.parent.parent

PROTO_DIR = Path(r"E:\touhou_work\garden\garden_svr_develop\proto")
PROTOC_EXE = PROJ_ROOT / "Assets" / "GameMain" / "SteamRes" / "Proto" / "protoc.exe"
GENERATED_DIR = Path(__file__).resolve().parent / "_generated"

# ── 包头常量 ──────────────────────────────────────────
HEADER_LENGTH = 22  # bytes
HEADER_STRUCT_FMT = ">IBBHiiHi"  # big-endian, 22 bytes total

# ServiceType 枚举（与 C# NetworkDefine 一致）
SERVICE_TYPE_UNDEFINED = 0
SERVICE_TYPE_LOGIC = 3
SERVICE_TYPE_CENT = 5
SERVICE_TYPE_SYNC = 6
SERVICE_TYPE_FIGHT = 8

# 心跳间隔（秒），与客户端 HeartBeatInterval 一致
HEARTBEAT_INTERVAL = 30

# TCP 接收缓冲区
TCP_RECV_BUFFER = 65536

# 登录超时
LOGIN_TIMEOUT = 10  # seconds

# ── MessageDefine 枚举 ────────────────────────────────
# 从 message_define.proto 中提取的完整枚举映射
MESSAGE_DEFINE = {
    # 内部使用
    "Nothing": 0,

    # 框架协议 10000+
    "Auto": 10000,
    "Login": 10001,
    "Logout": 10002,
    "NotifyFail": 10003,
    "HeartBeat": 10004,
    "SyncTrigger": 10005,
    "NotifyTestTrace": 10006,
    "NotifyIpRegion": 10007,
    "GetIpRegion": 10008,
    "FinishClientTask": 10009,
    "NotifySwitch": 10010,
    "UploadPlayAnalytics": 10011,
    "UploadPlayBehavior": 10012,

    # 内部协议
    "PostThinkingData": 10201,
    "PostWeixinSubscribe": 10202,
    "PostDouyinSubscribe": 10203,

    # 玩家协议 11000+
    "GetUserInfo": 11001,
    "NotifyCreated": 11002,
    "NotifySynced": 11003,
    "NotifyDailyUpdated": 11005,
    "UpdateGuide": 11006,
    "GetDetailPlayer": 11007,
    "NotifySetting": 11008,
    "UpdateSetting": 11009,
    "NotifyUserData": 11010,
    "Rename": 11011,
    "RandomName": 11012,
    "SearchPlayer": 11013,
    "NotifySdkStatData": 11014,
    "NotifyDelayMessage": 11015,
    "SendDelayMessage": 11016,
    "NotifyLevelExp": 11017,
    "NotifyPullDetailPlayer": 11018,
    "PassMainStory": 11020,

    # 玩家协议（道具）
    "NotifyUpdateProps": 11101,
    "NotifyReceiveProps": 11102,
    "PropOpenBox": 11104,
    "PropExchange": 11105,
    "DebugAddProp": 11106,
    "DeleteExpiredProp": 11107,
    "GetEneryStore": 11108,
    "GetTimeEnery": 11109,
    "NotifyPropFullInfo": 11111,
    "NotifyPropData": 11112,
    "NotifyPropConvert": 11113,

    # 签到协议
    "NotifySignFullInfo": 11120,
    "NotifySignData": 11121,
    "Sign": 11122,
    "ReSign": 11123,

    # 玩家协议（体力）
    "NotifyEnergy": 11151,

    # 称号
    "NotifyTitles": 11401,
    "SetTitleNotNew": 11402,
    "EquipTitle": 11403,

    # 头像
    "NotifyAvatar": 11411,
    "AvatarClearNew": 11412,
    "EquipAvatar": 11413,

    # 头像框
    "NotifyAvatarFrames": 11421,
    "SetAvatarFrameNotNew": 11422,
    "EquipAvatarFrame": 11423,

    # 气泡
    "NotifyBubbles": 11431,
    "SetBubbleNotNew": 11432,
    "EquipBubble": 11433,

    # 名帖
    "NotifyBackGrounds": 11441,
    "SetBackGroundNotNew": 11442,
    "EquipBackGround": 11443,

    # 社交 14000+
    "GetFriendList": 14001,
    "DeleteFriend": 14002,
    "ApplyAddFriend": 14003,
    "GetFriendApplyList": 14004,
    "AgreeFriendApply": 14005,
    "RefuseFriendApply": 14006,
    "NotifyFriendCount": 14007,
    "NotifyFriendBeDeleted": 14008,
    "NotifyFriendBeApplied": 14009,
    "NotifyFriendApplyAgreed": 14010,
    "NotifyFriendAddedResult": 14011,
    "NotifyFriendBriefInfo": 14012,
    "NotifyFriendData": 14013,
    "FriendSendGift": 14014,
    "FriendReceiveGift": 14015,
    "FriendSendAndReceiveGift": 14016,
    "NotifyFriendFullInfo": 14017,
    "FriendRecommendList": 14018,

    # 黑名单
    "GetBlacklist": 14051,
    "AddBlacklist": 14052,
    "DeleteBlacklist": 14053,
    "NotifyBlackBriefInfo": 14054,

    # 养殖 15000+
    "NotifyFarmlandFullInfo": 15001,
    "NotifyFarmland": 15002,
    "FarmlandStart": 15003,
    "FarmlandHarvest": 15004,
    "FarmlandCancel": 15005,
    "FarmlandUnlock": 15006,
    "FarmlandSpeedUp": 15007,
    "FarmlandWater": 15008,

    # 食材 16000+
    "NotifyIngredientFullInfo": 16001,
    "NotifyIngredient": 16002,
    "NotifyContainer": 16003,
    "NotifyIngredientData": 16004,
    "IngredientLevelUp": 16005,
    "GetIngredientCollectAward": 16006,
    "StartBreed": 16007,
    "SpeedUpBreed": 16008,
    "GetBreedAward": 16009,
    "NotifyBreedData": 16010,
    "NotifyDish": 16011,
    "GetDishExp": 16012,
    "IngredientRefine": 16013,
    "IngredientSaveRefine": 16014,

    # 菜肴台 17000+
    "NotifyDishTableFullInfo": 17001,
    "NotifyDishTable": 17002,
    "DishTableUnlock": 17003,
    "MakeDish": 17004,
    "DishTablePlate": 17005,
    "DishTableClear": 17006,
    "GetDishTableAward": 17007,

    # 订单 21000+
    "NotifyOrderFullInfo":18001,# 通知订单所有数据
    "NotifyOrderData":18002,    # 通知订单基础数据
    "NotifyResidentOrder":18003,     # 通知居民订单数据
    "NotifyScheduleOrder":18004,    # 通知宫廷订单数据
    "CompletedResidentOrder":18005,  # 完成居民订单
    "CompletedScheduleOrder":18006, # 完成预定订单
    "GetScheduleOrderLog":18007,# 拉取预定订单日志
    "RefreshScheduleOrder":18008, # 刷新预定订单
    "GetScheduleOrder":18009, # 拉取预定订单
    "NotifyGroupOrder":18010,# 通知组团订单数据
    "StartGroupOrder":18011, # 开始组团接单
    "CompletedGroupOrder":18012, # 完成组团订单
    "ChangeGroupOrder":18013, # 更换组团订单
    "GetGroupOrderReward":18014, # 领取组团订单奖励
    "NotifyCustomerOrder":18020,# 通知组团订单数据
    "CustomerPlaceOrder":18021, # 顾客下单
    "CompletedCustomerOrder":18022, # 交付顾客单

    # 功能 30000+
    # 邮件
    "NotifyMailFullInfo": 30001,
    "NotifyUpdateMail": 30003,
    "ReadMail": 30004,
    "DeleteMail": 30005,
    "ReceiveMail": 30006,
    "AutoDeleteMail": 30007,
    "SendSystemMail": 30008,

    # 任务系统
    "NotifyTaskFullInfo": 30301,
    "NotifyTaskData": 30302,
    "NotifyTask": 30303,
    "TaskReceiveReward": 30304,
    "NotifyTaskAutoReward": 30305,
    "TaskListReceiveReward": 30306,
    "NotifyMainTask": 30311,
    "MainTaskReceiveReward": 30312,
    "MissionTaskReceiveReward": 30313,
    "NotifyTarget": 30321,
    "TargetReceiveReward": 30322,

    # 抽奖/招募
    "Recruit": 30205,

    # 广告
    "NotifyUpdateAdsFullInfo": 30651,
    "NotifyUpdateAds": 30652,
    "NotifyAdsWxUnitId": 30653,
    "AdsClick": 30654,

    # 商店
    "NotifyShopFullInfo": 30901,
    "NotifyStoreGoods": 30902,
    "StoreBuy": 30903,
    "NotifyShop": 30904,
    "NotifyShopShelf": 30905,
    "ShopRefresh": 30906,
    "ShopBuy": 30907,
    "NotifyStoreData": 30908,

    # 抽奖
    "Lottery": 31803,

    # 充值 49000+
    "NotifyRechargeFullInfo": 49001,
    "NotifyCards": 49002,
    "BuyCard": 49003,
    "ReceiveCardDailyReward": 49004,
    "NotifyRechargeData": 49005,
    "NotifyDepositSuccess": 49006,
    "ReceiveFirstPaymentReward": 49007,

    # SDK 协议
    "DecryptWeixinData": 60101,
}

# ID → 名称 反向映射
ID_TO_NAME = {v: k for k, v in MESSAGE_DEFINE.items()}
