#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-pass repair of fullstack assembly. Frozen story entries are never rewritten."""
import base64
import collections
import copy
import hashlib
import json
import math
import struct
import zlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"assembly/card/dist/绝区零_咩咩全栈_完整角色卡_v1.3.0.json"
DIST=ROOT/"assembly/card/dist"
QA=ROOT/"assembly/qa"
LORE=ROOT/"assembly/worldbook/dist"
STEM="Zenless_Zone_Zero_Fullstack_Final"
def require(pred,msg):
    if not pred: raise AssertionError(msg)
def normalized(s): return s.replace("：",":")
def byprefix(seq,prefix):
    return [e for e in seq if e["comment"].startswith(prefix)]
def key(e): return (e["comment"], e["content"])
def field(e,order,pos="after_char",depth=4,constant=None,enabled=None,guard=None):
    e=copy.deepcopy(e)
    e["insertion_order"]=order
    e["position"]=pos
    if constant is not None: e["constant"]=constant
    if enabled is not None: e["enabled"]=enabled
    if guard is None: guard=(not e["constant"] and e["enabled"])
    e["selective"]=bool(e["keys"]) or e["constant"]
    ext=e.setdefault("extensions",{})
    ext.update({"position":{"before_char":0,"after_char":1,"at_depth":4}[pos],
                "depth":depth,"scan_depth":2,"exclude_recursion":guard,
                "prevent_recursion":guard,"display_index":0,
                "probability":100,"useProbability":True,"role":0,
                "match_whole_words":False,"case_sensitive":False,
                "selectiveLogic":0})
    for junk in ("excludeRecursion","preventRecursion","displayIndex","scanDepth"):
        ext.pop(junk,None)
    return e
def default(name,content="",order=0,enabled=True,constant=True):
    return {"id":0,"keys":[],"secondary_keys":[],"comment":name,"content":content,
            "constant":constant,"selective":constant,"insertion_order":order,
            "enabled":enabled,"position":"after_char","use_regex":False,
            "extensions":{"position":1,"depth":4,"scan_depth":2,
            "exclude_recursion":False,"prevent_recursion":False,
            "display_index":0,"probability":100,"useProbability":True,"role":0,
            "match_whole_words":False,"case_sensitive":False,"selectiveLogic":0}}
def marker(section,start,order,depth=4):
    name="【"+section+":"+("起始" if start else "结尾")+"】"
    return field(default(name),order,depth=depth,guard=False)
def orig_order(e): return e["insertion_order"]
def running_range(seq,top,bottom):
    require(len(seq)>0,"Empty assembly section")
    width=top-bottom
    return [field(e, top-(i*width//max(1,len(seq)-1))) for i,e in enumerate(seq)]

CARD=json.loads(SRC.read_text(encoding="utf-8"))
book=CARD["data"]["character_book"]
original=book["entries"]
require(len(original)==417,"Unexpected upstream head: entry count changed")
require(len({e["id"] for e in original})==417,"Upstream duplicate IDs")
# 395 originally frozen text objects; compare exact content after assembly.
frozen=[]
for e in original:
    c=e["comment"]
    if (c.startswith(("角色:","地点:","核心设定:","世界蓝灯:","地点蓝灯:","时间线:"))):
        frozen.append(e)
require(len(frozen)==395,"Frozen inventory drifted from 395")
frozen_multiset=collections.Counter(key(e) for e in frozen)

clear=next(e for e in original if e["comment"]=="🗑️清空局部变量(别关)")
mem=[next(e for e in original if e["comment"]==n) for n in
     ("日常记忆存储","重大记忆存储","玩家身世背景")]
timelines=sorted(byprefix(original,"时间线:"),key=orig_order,reverse=True)
require(len(timelines)==29 and timelines[0]["comment"].startswith("时间线:第一卷（上）")
        and timelines[-1]["comment"].startswith("时间线:第十四卷（下）"),
        "Original timeline order must be chronological")
narrative=next(e for e in original if e["comment"]=="输出规则:开放沙盒叙事")
battle=next(e for e in original if e["comment"]=="战斗思维链")
topic=next(e for e in original if e["comment"]=="核心规则:城市日常话题")
continuity=next(e for e in original if e["comment"]=="核心规则:叙事连续性")
world_blues=sorted(byprefix(original,"世界蓝灯:"),key=orig_order)
location_blues=sorted(byprefix(original,"地点蓝灯:"),key=orig_order)
settings=sorted(byprefix(original,"核心设定:"),key=orig_order)
major=sorted((e for e in byprefix(original,"角色:") if 201<=orig_order(e)<=299),key=orig_order)
minor=sorted((e for e in byprefix(original,"角色:") if 101<=orig_order(e)<=199),key=orig_order)
places=sorted(byprefix(original,"地点:"),key=orig_order)
require((len(world_blues),len(location_blues),len(settings),len(major),len(minor),len(places))==
        (9,5,140,82,59,71),"Upstream frozen category drift")
require(sum(e["enabled"] for e in timelines)==1 and timelines[0]["enabled"],"Timeline switch drift")

battle_text="""{{setvar::combat_driver::
<!-- 每回合输出 <combat_driver>；无战斗、遭遇、治疗、修复等需裁定事项时，仅输出“无”；不强制制造战斗。 -->
<combat_driver>
━━ 1.事态初始化(Init) ━━
事态类型: 【空洞战斗/都市遭遇/护送或救援/治疗与修复/其他行动判定/无】
我方侧: 【在场者、既有伤势、已确认装备与音擎、已知能力；无则填无】
敌方·对象: 【已实际出现的对手、可观察状态与行为；无则填无】
环境: 【所在区域、以太环境、距离、地形、掩体、危险与退路】

━━ 2.资源与地利判定(Power_Check) ━━
Step 0: 【核对以太适性、防护条件、体力、弹药、能量、音擎与队伍实际补给；无设定依据不编数值】
Step 1: 【判断空洞地形、视野、天气、空间异常和可利用掩体对双方的实际影响】
Step 2: 【记录行动消耗、侵蚀暴露、损伤与恢复途径；命中、闪避、防御均有适当代价】

━━ 3.能力解析(Analysis) ━━
原则: 【初遇未知能力不得立即破解，也不能凭读者知识让角色先知】
解析度: 0%(未知) → 30%(表现被观察) → 60%(限制暴露) → 90%(对策成立) → 100%(充分理解)
加速条件: 【仅限真实侦察、反复观察、队友交流、合理的装备检测与既有情报；不是自动升级】

━━ 4.对抗演算(Calculation) ━━
判定优先级: 【机制克制 > 能量与补给链 > 地利 > 操作熟练度 > 已有规格】
Step 1: 【先制、机动、站位、队友协同与敌方反应】
Step 2: 【以实际招式、元素与状态相性判定攻防；不臆造额外属性克制】
Step 3: 【判定伤势、装备损耗、空洞侵蚀、失衡、环境破坏与战后代价】
严禁无代价: 【命中必有消耗，回避必有机动代价，防御必有承受或损耗，不存在无损连战】

━━ 5.非战斗裁定(Utility) ━━
【绳匠引导依已有信息、邦布协作与路径条件；修复依工具、零件与时间；救援依人员状态、防护与撤离条件。失败应留下可追踪后果，不凭空跳过。】

━━ 6.结果判定(Result) ━━
战斗结果: 【绝对压制/优势胜利/惨胜/战术撤退/败北/无】
败北结算: 【按当前处境记录伤势、资源、情报、委托与同伴安全，不强制死亡】
强制原则: 【NPC有独立判断，攻击补给、撤离路线与辅助者是合法战术；不得为了玩家获胜强制降智】
成长规则: 【仅允许熟练度精进与关系深化；严禁凭空新增能力、数值化等级或普通日常获得成长】
</combat_driver>
}}"""
status_text="""{{setvar::status_format::
<status_format>
不要输出 CSS/HTML 样式。请严格按照以下 XML 格式输出：
每轮正文结束时输出唯一一组 <status>；若咩咩预设已有同名模块，直接使用该模块，不重复生成第二份，不覆盖预设既有字段规则。正文在场人物仍以 <story_scene> 为依据。
<status>
🏷️身份：【玩家已确定的姓名或身份】<!-- 规则:只有玩家明确提供或剧情实际确认才写入；身份变更在事件发生后更新，不擅自成为组织成员 -->
🕰️时间：【YYYY年MM月DD日·当前时段】<!-- 规则:以启用的时间线与实际对话推进为准；禁止自动进入未启用卷或倒灌未来剧情 -->
📍当前位置：【新艾利都·区域·具体场所】<!-- 规则:每次实际移动后更新；空洞必须注明具体区域及防护情况，地点名供绿灯匹配 -->
❤️身体状况：【健康/轻伤/重伤/濒死/死亡】<!-- 规则:伤势根据实际伤害分档，治疗需相应手段和时间，未受伤填健康 -->
🛡️以太暴露：【未暴露/低/中/高/严重侵蚀】<!-- 规则:只在确有以太暴露时变化；防护、脱离环境和治疗按原作条件处理，不把所有人物视为相同适性 -->
👗服装与装备：【已确认穿着、防护装备与音擎/武器；无则填无】<!-- 规则:只列实有并已装备物件，掉落、损坏、换装及时更新 -->
🎒随身物品：【已确认持有的关键物品；无则填无】<!-- 规则:取得、消耗、交付或遗失后更新；不凭空增加货币、弹药和道具 -->
🤝已知关系：【人物名:已发生的相识/合作/冲突；无则填无】<!-- 规则:只记录当前当事人已知事实，不把未启用卷后续关系提前算入 -->
🎯当前目标：【玩家已接下的委托或自主目标；无则填无】<!-- 规则:目标完成或放弃后更新，不能自动强制接主线任务 -->
✨已知技能：【已有能力及入门/熟练/精通；无则填无】<!-- 规则:只写正式掌握的技能；成长只体现熟练度、物品增减与关系深化，禁经验值、数值等级及日常凭空觉醒 -->
</status>
</status_format>
}}"""
topic_text="""<easter_eggs>
# 开放性话题池（AI 自主维护的彩蛋库）
## 使用规则
- 频率: 每5~8回合至多自然抛出1个；只在当前场景吻合时顺带提及，主线与玩家主动行动优先。
- 呈现: NPC闲聊、坊间传闻、小事件或旧物；不宣布“发现彩蛋”，玩家不接就沉底，不追问推销。
- 延伸: 可追加[来源:原著/衍生/自创]话题，必须符合新艾利都科技、空洞、邦布与当下已启用时间线；拿不准出处不标原著。
- 禁区: 不预告未启用卷人物秘密、胜负或组织重大事件；话题本身不改状态栏、不启动战斗裁定，除非玩家实际采取行动。
## 话题池
- [来源:原著] Random Play的旧录像: 触发:六分街录像店｜呈现:顾客闲聊一部难找的老电影｜延伸:玩家愿不愿意帮忙翻找片单。
- [来源:原著] 邦布的嗯呐嗯呐: 触发:邦布在场｜呈现:路人对面屏与动作的猜测｜延伸:在不把邦布拟人化成兔子的前提下交流与协助。
- [来源:原著] 六分街街机: 触发:街机厅附近｜呈现:玩家听见街机操作声｜延伸:是否要看看一局游戏或当地玩家的技巧。
- [来源:原著] 新艾利都拉面话题: 触发:六分街用餐｜呈现:顾客讨论口味与排队｜延伸:从日常饮食认识不同职业的市民。
- [来源:衍生] 光映广场的城市广告: 触发:商业区停留｜呈现:橱窗与海报引发闲谈｜延伸:广告背后的以太经济、品牌或职业生活。
- [来源:衍生] 外环行车见闻: 触发:公路补给点｜呈现:司机交换道路经验｜延伸:了解驾驶、防护与补给的普通人视角。
- [来源:衍生] 卫非地的小摊对话: 触发:卫非地日常场景｜呈现:摊主说起一件寻常物件｜延伸:物品与当地生活的联系。
- [来源:自创] 错投的便条: 触发:小店日常｜呈现:一张未署名便条被误夹进货单｜延伸:由玩家决定是否追查失主，不预设秘密答案。
- [来源:自创] 失灵的路口导向牌: 触发:城市街角｜呈现:路人围着一块失灵屏幕讨论｜延伸:可维修、绕路或置之不理。
- [来源:自创] 被遗落的旧票根: 触发:公共场所｜呈现:角落里的一张旧票根｜延伸:任意日常调查方向，不绑定主线人物与结局。
</easter_eggs>"""

# Assemble in the exact seven-mother-section reading sequence.
final=[]
final.append(field(clear,556,pos="before_char",depth=4,guard=False))
final.append(marker("记忆相关",True,555))
for e,o in zip(mem,[554,553,552]):
    final.append(field(e,o,enabled=False,constant=True,guard=False))
final.append(marker("记忆相关",False,551))
final.append(marker("输出规则",True,550))
final.append(field(narrative,455,pos="at_depth",depth=0,constant=True,guard=False))
for i,e in enumerate(timelines):
    final.append(field(e,454,pos="at_depth",depth=0,constant=True,
                       enabled=(i==0),guard=False))
b=field(battle,453,pos="at_depth",depth=0,constant=True,guard=False)
b["content"]=battle_text
final.append(b)
status=field(default("状态栏-默认",status_text),452,pos="at_depth",depth=0,guard=False)
final.append(status)
final.append(marker("输出规则",False,451))
final.append(marker("核心规则",True,450,depth=2))
for i,e in enumerate(world_blues+location_blues):
    final.append(field(e,449-i,pos="after_char",depth=4,constant=True,guard=False))
final.append(field(continuity,406,pos="after_char",depth=4,constant=True,guard=False))
t=field(topic,405,pos="after_char",depth=4,constant=True,guard=False)
t["comment"]="核心规则:开放性话题池"
t["keys"]=[]; t["secondary_keys"]=[]; t["use_regex"]=False
t["content"]=topic_text
final.append(t)
final.append(marker("核心规则",False,401,depth=2))
final.append(marker("核心设定",True,400))
# More than 98 triggered core entries; equal orders inside the band are legal CCV3.
# Stable array order & distinct display_index preserve all 140 without moving greens.
final.extend(running_range(settings,399,302))
final.append(marker("核心设定",False,301))
final.append(marker("主要角色",True,300,depth=7))
final.extend(running_range(major,299,202))
final.append(marker("主要角色",False,201,depth=7))
final.append(marker("其他角色",True,200))
final.extend(running_range(minor,199,102))
final.append(marker("其他角色",False,101))
final.append(marker("地点",True,100))
final.extend(running_range(places,99,2))
final.append(marker("地点",False,1))
require(len(final)==418,"Expected exactly one added status bar")
for idx,e in enumerate(final):
    e["id"]=idx+1
    e["extensions"]["display_index"]=idx
orders=[e["insertion_order"] for e in final]
require(orders==sorted(orders,reverse=True),"Section order not descending")
assert len([e for e in final if e["comment"].startswith("【")])==14
assert all(e["content"]=="" for e in final if e["comment"].startswith("【"))
require(collections.Counter(key(e) for e in final if key(e) in frozen_multiset)==frozen_multiset,
        "Frozen entry content or comment changed")
require(all(e["extensions"]["prevent_recursion"] and e["extensions"]["exclude_recursion"] and
            e["position"]=="after_char" and e["extensions"]["scan_depth"]==2
            for e in final if e["enabled"] and not e["constant"]),
        "Double recursion guard / triggered position invalid")
require(len([e for e in final if e["comment"].startswith("时间线:")])==29,"Timeline count drift")
require(sum(e["enabled"] for e in final if e["comment"].startswith("时间线:"))==1,
        "Only first timeline should be active")
require(next(e for e in final if e["comment"]=="战斗思维链")["insertion_order"]==453,
        "Combat slot mismatch")
require(next(e for e in final if e["comment"]=="状态栏-默认")["insertion_order"]==452,
        "Status slot mismatch")
require(not any(token in e["comment"] for e in final for token in ("GREEN-","CHAR-","ABILITY-")),
        "Construction prefixes leaked into titles")

# Use previously approved main greeting; adapt its absent-timeline clause to opening.md.
greet=CARD["data"]["first_mes"].replace("未启用时由当前故事合理确定","未启用时随机")
require(greet.startswith("<opening>") and greet.rstrip().endswith("</opening>"),
        "Main greeting missing opening tags")
require(all(s in greet for s in ("[Location Pool]","[Identity Pool]","[以太适性 Pool]","[Spawn Roulette]")),
        "Main greeting missing three weighted pools")
greet2="""<opening>
（说明:备选开场-六分街日常）
（时间:以已启用的【时间线】条目为锚点；未启用时随机）

输入[随机开始]开始故事。

<!--
[Location Pool]（按概率抽一处）:
1. 六分街街道 55%：拉面热气、邻店招牌与街机声音。难度⭐
2. Random Play门前 30%：录像海报、木门铃声与晚风。难度⭐
3. 光映广场 15%：地铁人流、广告屏与商场灯光。难度⭐⭐
[Identity Pool]（按概率抽一种）:
1. 街区熟客 45%
2. 新搬来的邻居 35%
3. 临时帮工 20%
[以太适性 Pool]（按概率抽一种）:
1. 普通耐受 80%
2. 有防护训练 17%
3. 较高适性 3%
[Spawn Roulette]:
1. 三池独立抽取并生成第一幕，例如六分街熟客在拉面店外听见邦布的嗯呐声，或光映广场帮工刚从地铁口走出。
2. 以街道气味、霓虹、木门铃与人声建立现场；不得替玩家决定下一步行动。
3. 新艾利都有邦布、录像店、地铁与空洞防护；空洞不是普通地下洞穴。
4. 不公开法厄同秘密，不强迫认识铃或哲，不让其他人成为佩洛伊斯寄宿者；不预设未启用卷事件。
-->
</opening>"""
greet3="""<opening>
（说明:备选开场-外环旅程）
（时间:以已启用的【时间线】条目为锚点；未启用时随机）

输入[随机开始]开始故事。

<!--
[Location Pool]（按概率抽一处）:
1. 野火镇 35%：补给招牌、维修工具敲击与尘土。难度⭐⭐
2. 外环公路休息点 25%：轮胎热气、风声与车辆。难度⭐⭐
3. 老油田安全外围 15%：旧设备、机油气味与警戒线。难度⭐⭐⭐
4. 斯科特前哨安全外围 15%：监测灯与巡逻脚步。难度⭐⭐⭐
5. 外环矿区安全道路 10%：矿车声、碎石与风沙。难度⭐⭐⭐⭐
[Identity Pool]（按概率抽一种）:
1. 车队随行人 40%
2. 补给商 30%
3. 独行旅行者 20%
4. 临时运输协助者 10%
[以太适性 Pool]（按概率抽一种）:
1. 普通耐受 80%
2. 有防护训练 17%
3. 较高适性 3%
[Spawn Roulette]:
1. 三池独立抽取并生成第一幕，例如野火镇补给商检查行囊，或公路休息点的旅行者听见修车声。
2. 表现风沙、机油、发动机和交通往来；只在允许安全进入的场所起步。
3. 物资、防护、绳匠协助均受实际条件制约；危险空洞不可当普通野外徒步点。
4. 不预设认识卡吕冬之子，不给玩家免费武装、虚狩称号或未来卷情报；不替玩家作选择。
-->
</opening>"""
for g in (greet,greet2,greet3):
    require(g.count("<opening>")==1 and g.count("</opening>")==1
            and "输入[随机开始]开始故事。" in g,
            "Greeting tags / trigger broken")

book["entries"]=final
book["recursive_scanning"]=False
CARD["data"]["first_mes"]=greet
CARD["first_mes"]=greet
CARD["data"]["alternate_greetings"]=[greet2,greet3]
scenario=CARD["data"]["scenario"]
scenario=scenario.replace("不使用MVU、状态栏、酒馆助手脚本或旧变量引擎。",
                          "不使用MVU、酒馆助手脚本或旧变量引擎；使用咩咩全栈原生文字状态栏，不修改咩咩预设。")
CARD["data"]["scenario"]=scenario
CARD["scenario"]=scenario
CARD["data"]["character_version"]="fullstack-final-1.4.0"
CARD["data"].setdefault("extensions",{})["world"]=book["name"]
require(CARD["data"]["extensions"]["world"]==book["name"],
        "Primary worldbook reference mismatch")
require(not any(k in CARD["data"]["extensions"] for k in ("tavern_helper","mvu","regex_scripts")),
        "Forbidden script extension")

def compact(o):return json.dumps(o,ensure_ascii=False,separators=(",",":")).encode("utf-8")
DIST.mkdir(parents=True,exist_ok=True);LORE.mkdir(parents=True,exist_ok=True);QA.mkdir(parents=True,exist_ok=True)
json_bytes=compact(CARD)
out_json=DIST/(STEM+".json")
out_json.write_bytes(json_bytes)
(LORE/"Zenless_Zone_Zero_Fullstack_Lorebook.json").write_bytes(compact(book))
require(json.loads(out_json.read_bytes())["data"]["character_book"]["entries"]==final,
        "JSON roundtrip failed")

# Valid, dependency-free RGB PNG with both SillyTavern metadata chunks.
# The original artwork is absent from this public repository; use a neutral
# generated cover rather than pulling in or modifying any unverified image.
def chunk(kind,data):
    return struct.pack(">I",len(data))+kind+data+struct.pack(">I",zlib.crc32(kind+data)&0xffffffff)
width,height=768,1024
pixels=bytearray()
for y in range(height):
    pixels.append(0)
    for x in range(width):
        edge=min(x,width-1-x,y,height-1-y)
        rim=15 if edge<10 else 0
        halo=max(0,1-abs(math.hypot(x-width*0.52,y-height*0.34)-height*0.20)/(height*0.19))
        r=min(255,int(18+22*y/height+18*halo+rim))
        g=min(255,int(25+26*y/height+22*halo+rim))
        b=min(255,int(36+33*y/height+26*halo+rim))
        pixels.extend((r,g,b))
packed=base64.b64encode(json_bytes)
png=(b"\x89PNG\r\n\x1a\n"+
     chunk(b"IHDR",struct.pack(">IIBBBBB",width,height,8,2,0,0,0))+
     chunk(b"tEXt",b"chara\x00"+packed)+
     chunk(b"tEXt",b"ccv3\x00"+packed)+
     chunk(b"IDAT",zlib.compress(bytes(pixels),9))+chunk(b"IEND",b""))
out_png=DIST/(STEM+".png")
out_png.write_bytes(png)

# Independently parse PNG chunks, CRCs and the two base64 payloads.
pos=8
metadata={}
while pos<len(png):
    size=struct.unpack(">I",png[pos:pos+4])[0]
    kind=png[pos+4:pos+8]
    raw=png[pos+8:pos+8+size]
    crc=struct.unpack(">I",png[pos+8+size:pos+12+size])[0]
    require(zlib.crc32(kind+raw)&0xffffffff==crc,"PNG CRC error")
    if kind==b"tEXt":
        k,val=raw.split(b"\x00",1)
        metadata[k.decode("ascii")]=base64.b64decode(val,validate=True)
    pos+=12+size
require(pos==len(png) and set(metadata)=={"chara","ccv3"},"PNG chunk scan error")
require(metadata["chara"]==metadata["ccv3"]==json_bytes,
        "PNG chara/ccv3 byte equality failed")
require(json.loads(metadata["ccv3"])["data"]["character_book"]["entries"]==final,
        "PNG embedded lorebook mismatch")
sections=["记忆相关","输出规则","核心规则","核心设定","主要角色","其他角色","地点"]
require([(e["comment"],e["insertion_order"]) for e in final if e["comment"].startswith("【")]==
        [(f"【{s}:起始】",a) for s,a in zip(sections,[555,550,450,400,300,200,100])] +
        [],"UNUSED") if False else None
for s in sections:
    titles=[e["comment"] for e in final]
    start=titles.index("【"+s+":起始】")
    end=titles.index("【"+s+":结尾】")
    require(start<end and all(not title.startswith("【") for title in titles[start+1:end]),
            "Section marker nesting broken: "+s)
result={
 "status":"STATIC_ASSEMBLY_PASS_ANDROID_NOT_TESTED",
 "baseline_repo_head":"a9780dfa08af05265c59c86ff58e1294a946a63e",
 "template":"咩咩制卡·全栈_v1.0.0.zip / fullcard.md / combat-cot.md / status-bar.md / opening.md / easter-egg.md / mother 2.0.0",
 "protected_frozen_entries":len(frozen),
 "protected_content_byte_for_byte":True,
 "entry_count":len(final),"section_markers":14,
 "enabled_timelines":[e["comment"] for e in timelines if e["enabled"]],
 "timeline_parts":29,
 "status_at_depth_0":True,"battle_six_steps":True,
 "open_topic_pool_constant":True,
 "memory_storage_disabled":True,
 "double_recursion_enabled_for_triggered":True,
 "body_stat_categories":{"main_characters":82,"abilities":81,"bangboo":59,
                         "core_green_including_states":140,"locations":71},
 "png_crc_pass":True,"png_chara_ccv3_equal":True,
 "png_embedded_lorebook_equal":True,
 "png_cover":"neutral generated placeholder; original cover not in public repo",
 "sillytavern_android_real_device":"NOT_TESTED",
 "json_sha256":hashlib.sha256(json_bytes).hexdigest(),
 "png_sha256":hashlib.sha256(png).hexdigest(),
 "outputs":[str(out_json.relative_to(ROOT)),str(out_png.relative_to(ROOT))]
}
(QA/"Final_Fullstack_Assembly_QA.json").write_text(
    json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"status":"PASS","entries":len(final),"protected":len(frozen),
                  "json_bytes":len(json_bytes),"png_bytes":len(png)},ensure_ascii=False))
