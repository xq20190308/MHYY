import httpx
import json
import os
import re
import sentry_sdk
import random
import time
import yaml


config_datas = """
# 使用前请阅读文档：https://bili33.top/posts/MHYY-AutoCheckin-Manual-Gen2/
# 有问题请前往Github开启issue：https://github.com/GamerNoTitle/MHYY/issues

######## 以下为账号配置项，可以多账号，详情请参考文档 ########
accounts:
  # 第一个账号
  - token: 
    # 关于type：如果你在安卓版的云·原神里面抓的话type应该是2
    # 如果你是网页版抓的，那type应该是16
    # 此处仅供参考，具体以你抓的为准 
    type: 
    # sysver：如果你是安卓版抓的，这个应该会显示你的安卓版本（鸿蒙不清楚，手上没设备）
    # 如果你是网页版抓的，这个应该是你的系统版本（注：Windows 10和Windows 11都是写的Windows 10）
    sysver: 
    # deviceid：手机抓的会有这个，抓到什么填什么
    # 如果是网页版抓的，那也是抓到什么填什么
    deviceid: 
    # devicename: 手机抓的话就是手机的入网型号，如红米K40为M2012K11AC，红米K50为22021211RC
    # 如果是网页版抓的，填Unknown
    devicename: 
    # devicemodel: 手机抓的填抓出来的手机型号，大概为手机厂商+上面的deviceid，如红米K40为Xiaomi M2012K11AC
    # 如果是网页版抓的，填Unknown
    devicemodel: 
    # appid: 国服手机抓的固定填1953439974，网页版抓的留空；国际服手机抓的填600493
    appid: 
    # region(可选): 账号所处的地区，国服填cn，国际服填os，不填或非法值按国服处理
    region: cn
"""

sentry_sdk.init(
    "https://425d7b4536f94c9fa540fe34dd6609a2@o361988.ingest.sentry.io/6352584",
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    # We recommend adjusting this value in production.
    traces_sample_rate=1.0,
)

class RunError(Exception):
    pass


def handler(*args):
    # Options
    sct_status = os.environ.get("sct")  # https://sct.ftqq.com/
    sct_key = os.environ.get("sct_key")
    sct_url = f"https://sctapi.ftqq.com/{sct_key}.send?title=MHYY-AutoCheckin 自动推送"

    sct_msg = ""

    conf = yaml.load(config_datas, Loader=yaml.FullLoader)
    print(conf)
    if not conf:
        print("请正确配置环境变量或者config.yml后再运行本脚本！")
        os._exit(0)
    print(f"检测到 {len(conf)} 个账号，正在进行任务……")

    try:
        ver_info = httpx.get(
            "https://hyp-api.mihoyo.com/hyp/hyp-connect/api/getGameBranches?game_ids[]=1Z8W5NHUQb&launcher_id=jGHBHlcOq1",
            timeout=60,
            verify=False,
        ).text
        version = json.loads(ver_info)["data"]["game_branches"][0]["main"]["tag"]
        print(f"从官方API获取到云·原神最新版本号：{version}")
    except Exception as e:
        version = "5.0.0"

    for config in conf["accounts"]:
        # 各种API的URL
        NotificationURL = "https://api-cloudgame.mihoyo.com/hk4e_cg_cn/gamer/api/listNotifications?status=NotificationStatusUnread&type=NotificationTypePopup&is_sort=true"
        WalletURL = "https://api-cloudgame.mihoyo.com/hk4e_cg_cn/wallet/wallet/get"
        AnnouncementURL = (
            "https://api-cloudgame.mihoyo.com/hk4e_cg_cn/gamer/api/getAnnouncementInfo"
        )

        if config == "":
            # Verify config
            raise RunError(
                f"请在Settings->Secrets->Actions页面中新建名为config的变量，并将你的配置填入后再运行！"
            )
        else:
            token = config["token"]
            client_type = config["type"]
            sysver = config["sysver"]
            deviceid = config["deviceid"]
            devicename = config["devicename"]
            devicemodel = config["devicemodel"]
            appid = config["appid"]
        headers = {
            "x-rpc-combo_token": token,
            "x-rpc-client_type": str(client_type),
            "x-rpc-app_version": str(version),
            "x-rpc-sys_version": str(
                sysver
            ),  # Previous version need to convert the type of this var
            "x-rpc-channel": "cyydmihoyo",
            "x-rpc-device_id": deviceid,
            "x-rpc-device_name": devicename,
            "x-rpc-device_model": devicemodel,
            "x-rpc-vendor_id": "1",  # 2023/8/31更新，不知道作用
            "x-rpc-cg_game_biz": "hk4e_cn",  # 游戏频道，国服就是这个
            "x-rpc-op_biz": "clgm_cn",  # 2023/8/31更新，不知道作用
            "x-rpc-language": "zh-cn",
            "Host": "api-cloudgame.mihoyo.com",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
        }
        bbsid = re.findall(r"oi=[0-9]+", token)[0].replace("oi=", "")
        region = config.get("region", "cn")
        if region == "os":
            # 国际服处理
            headers["x-rpc-channel"] = "mihoyo"
            headers["x-rpc-cg_game_biz"] = "hk4e_global"
            headers["x-rpc-op_biz"] = "clgm_global"
            headers["x-rpc-cg_game_id"] = "9000254"
            headers["x-rpc-app_id"] = "600493"
            headers["User-Agent"] = "okhttp/4.10.0"
            headers["Host"] = "sg-cg-api.hoyoverse.com"
            # 国际服URL
            NotificationURL = "https://sg-cg-api.hoyoverse.com/hk4e_global/cg/gamer/api/listNotifications?status=NotificationStatusUnread&type=NotificationTypePopup&is_sort=true"
            WalletURL = (
                "https://sg-cg-api.hoyoverse.com/hk4e_global/cg/wallet/wallet/get"
            )
            AnnouncementURL = "https://sg-cg-api.hoyoverse.com/hk4e_global/cg/gamer/api/getAnnouncementInfo"

        print(
            f"正在进行第 {conf['accounts'].index(config) +1 } 个账号，服务器为{'CN' if region != 'os' else 'GLOBAL'}……"
        )

        wallet = httpx.get(WalletURL, headers=headers, timeout=60, verify=False)
        print(wallet.text)
        if json.loads(wallet.text) == {
            "data": None,
            "message": "登录已失效，请重新登录",
            "retcode": -100,
        }:
            print(f"当前登录已过期，请重新登陆！返回为：{wallet.text}")
            sct_msg += f"当前登录已过期，请重新登陆！返回为：{wallet.text}"
        else:
            print(
                f"你当前拥有免费时长 {json.loads(wallet.text)['data']['free_time']['free_time']} 分钟，畅玩卡状态为 {json.loads(wallet.text)['data']['play_card']['short_msg']}，拥有米云币 {json.loads(wallet.text)['data']['coin']['coin_num']} 枚"
            )
            sct_msg += f"你当前拥有免费时长 {json.loads(wallet.text)['data']['free_time']['free_time']} 分钟，畅玩卡状态为 {json.loads(wallet.text)['data']['play_card']['short_msg']}，拥有米云币 {json.loads(wallet.text)['data']['coin']['coin_num']} 枚"
            announcement = httpx.get(
                AnnouncementURL, headers=headers, timeout=60, verify=False
            )
            print(f'获取到公告列表：{json.loads(announcement.text)["data"]}')
            res = httpx.get(NotificationURL, headers=headers, timeout=60, verify=False)
            success, Signed = False, False
            try:
                if list(json.loads(res.text)["data"]["list"]) == []:
                    success = True
                    Signed = True
                    Over = False
                elif json.loads(json.loads(res.text)["data"]["list"][0]["msg"]) == {
                    "num": 15,
                    "over_num": 0,
                    "type": 2,
                    "msg": "每日登录奖励",
                    "func_type": 1,
                }:
                    success = True
                    Signed = False
                    Over = False
                elif (
                    json.loads(json.loads(res.text)["data"]["list"][0]["msg"])[
                        "over_num"
                    ]
                    > 0
                ):
                    success = True
                    Signed = False
                    Over = True
                else:
                    success = False
            except IndexError:
                success = False
            if success:
                if Signed:
                    print(f"获取签到情况成功！今天是否已经签到过了呢？")
                    sct_msg += f"获取签到情况成功！今天是否已经签到过了呢？"
                    print(f"完整返回体为：{res.text}")
                elif not Signed and Over:
                    print(
                        f'获取签到情况成功！当前免费时长已经达到上限！签到情况为{json.loads(res.text)["data"]["list"][0]["msg"]}'
                    )
                    sct_msg += f'获取签到情况成功！当前免费时长已经达到上限！签到情况为{json.loads(res.text)["data"]["list"][0]["msg"]}'
                    print(f"完整返回体为：{res.text}")
                else:
                    print(
                        f'获取签到情况成功！当前签到情况为{json.loads(res.text)["data"]["list"][0]["msg"]}'
                    )
                    sct_msg += f'获取签到情况成功！当前签到情况为{json.loads(res.text)["data"]["list"][0]["msg"]}'
                    print(f"完整返回体为：{res.text}")
            else:
                raise RunError(
                    f"签到失败！请带着本次运行的所有log内容到 https://github.com/GamerNoTitle/MHYY/issues 发起issue解决（或者自行解决）。签到出错，返回信息如下：{res.text}"
                )
        if sct_status:
            res = httpx.post(
                sct_url,
                json={
                    "title": "",
                    "short": "MHYY-AutoCheckin 签到情况报告",
                    "desp": sct_msg,
                },
                timeout=30,
            )
            if res.status_code == 200:
                print("sct推送完成！")
            else:
                print("sct无法推送")
                print(res.text)
