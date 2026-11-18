---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 4089e70912072d5b0de62543257d198b_0e61a41ddc4c11f19232525400248c00
    ReservedCode1: rv9ugh2Ur7lxBuL41ZN94vs7ua/O5VYlSzAflCkwDqKfZZXW+/uYPb9sgxSSlKz9HFrmUHdsZzPplJCXjQISY7XoqERPTpZqf3tbE5cLMa7+v0/kbysbrO1tAWHCO+SalPnG606Xze7zABpuB8Qxes/+7nK8GAyQ497NtZY2KwAVw+SQEyRi/Ta/1JI=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 4089e70912072d5b0de62543257d198b_0e61a41ddc4c11f19232525400248c00
    ReservedCode2: rv9ugh2Ur7lxBuL41ZN94vs7ua/O5VYlSzAflCkwDqKfZZXW+/uYPb9sgxSSlKz9HFrmUHdsZzPplJCXjQISY7XoqERPTpZqf3tbE5cLMa7+v0/kbysbrO1tAWHCO+SalPnG606Xze7zABpuB8Qxes/+7nK8GAyQ497NtZY2KwAVw+SQEyRi/Ta/1JI=
---

﻿# 鑸┖鍙戝姩鏈哄皝闂紡绂诲績鍙惰疆璁捐璇存槑涔?
**浠诲姟**锛氶棴鐜紙灏侀棴寮忥級绂诲績鍙惰疆鑷富璁捐 鈥?mdot 2.0 kg/s锛孴01 288.15 K锛孭01 101.325 kPa锛屜€ 鈮?4.0锛孴i-6Al-4V锛孎OS 鈮?1.5锛屽皝闂嫇鎵戯紙hub disk + shroud + Z 鐗囧悗寮彾鐗囷級锛屽彲鍒堕€犮€?**鏃ユ湡**锛?026-11-09
**妯″瀷**锛歚virtu-ties-v1:latest`锛圤llama 11435 瀹炰緥锛?**鍒ゅ畾鍣?*锛歚scripts/closed_impeller_proctor.py::ruler()` 鈥?鐙珛灏哄瓙锛屽垽瀹氭潈鐙崰
**鎶ュ憡**锛歚report_Aprime_auto_virtu-ties-v1_latest_20261109_224251.json`

---

## 1. 鍒ゅ畾缁撹

| 椤?| 缁撴灉 |
|---|---|
| ruler 杩濊 | **0 椤?* |
| passed | **True** |
| 澶嶇畻鍘嬫瘮 蟺_c | **4.010**锛堣姹?鈮?4.0锛岀孩绾?鈮?3.96锛?|
| 鍙跺皷閫?u2 | **464.23 m/s**锛團OS 鍙嶈В纭笂闄?514.13锛?|
| 杞瓙 FOS | **1.84**锛堣姹?鈮?1.5锛?|
| 鐩稿椹但鏁?M_rel,tip | **1.08**锛堢孩绾?鈮?1.15锛?|
| 鎷撴墤 | 灏侀棴锛岀敱 STL 瀹炴祴 |
| 鍒嗚处 | 璁捐鍙傛暟鐢辩‘瀹氭€ф眰瑙ｅ櫒鍙嶈В锛屾ā鍨嬫彁渚?6 涓嚜鐢卞害锛堣 搂6锛?|

---

## 2. 璁捐鍙傛暟锛?7 瀛楁锛屽叏閮ㄤ负鎻愪氦鍊硷級

| 瀛楁 | 鍊?| 璇存槑 |
|---|---|---|
| `D2_mm` | 220.0 | 鍙惰疆澶栧緞 |
| `N_rpm` | 40300.5 | 杞€?|
| `Z_blades` | 12 | 鍚庡集鍙剁墖鏁?|
| `beta2b_deg` | 25.0 | 鍑哄彛鍙剁墖瑙掞紙鍚庡集锛?|
| `b2_mm` | 19.8 | 鍑哄彛娴侀亾瀹斤紙b2/D2 = 0.090锛?|
| `D1t_mm` | 166.03 | 杩涘彛鍙跺皷鐩村緞 |
| `D1h_mm` | 76.5 | 杩涘彛杞瘋鐩村緞 |
| `axial_length_mm` | 82.5 | 杞村悜闀垮害锛?.375路D2锛屽尯闂翠腑鍊硷級 |
| `shroud_thickness_mm` | 2.0 | 杞洊鍘?|
| `blade_thickness_mm` | 1.8 | 鍙剁墖鍘?|
| `hub_disk_thickness_mm` | 8.0 | 杞瘋鐩樺帤 |
| `bore_diameter_mm` | 26.4 | 涓績瀛斿緞 |
| `fillet_root_mm` | 1.2 | 鍙舵牴鍦嗚 |
| `eta_total` | 0.85 | 鍋囪鎬绘晥鐜?|
| `claimed_pressure_ratio` | 4.010 | 鐢卞昂瀛愬绠楁淳鐢?|
| `claimed_tip_speed_m_s` | 464.23 | 鐢卞昂瀛愬绠楁淳鐢?|
| `claimed_FOS` | 1.84 | 鐢卞昂瀛愬绠楁淳鐢?|

**鐩村緞搴?*锛歜ore 26.4 < D1h 76.5 < D1t 166.03 < D2 220.0 鉁?
---

## 3. 灏哄瓙澶嶇畻鐨勭墿鐞嗛噺锛堥潪妯″瀷瀹ｇО锛?
| 閲?| 鍊?| 鍙ｅ緞 |
|---|---|---|
| u2 鍙跺皷閫?| 464.23 m/s | 瑙ｆ瀽澶嶇畻 |
| 婊戠Щ鍥犲瓙 蟽 | 0.8328 | Wiesner: 蟽 = 1 鈭?鈭?cos尾2b)/Z^0.7 |
| 绛夌喌鐒撳崌 螖h0 | 165.85 kJ/kg | analytic_recomputed |
| 鍘嬫瘮 蟺_c | 4.0099 | 杩涘彛-鍑哄彛杩唬 |
| 鍑哄彛寰勫悜鍒嗛€?cm2 | 75.57 m/s | 璐ㄩ噺杩炵画 |
| 绛夋晥搴斿姏 蟽_eq | 478.31 MPa | (3+谓)/8路蟻路u2虏路K_blade |
| FOS | 1.8398 | 蟽_y 880 / 蟽_eq |
| 杩涘彛杞村悜閫?ca1 | 100.0 m/s | 鐢卞枆鍙ｉ潰绉弽瑙?|
| M_rel,tip | 1.08 | 鈭?ca1虏+u1t虏)/鈭?纬RT1) |
| 姣旇浆閫?Ns | 0.741 | rad/s 鍩?|
| 鍑哄彛鎬绘俯 T02 | 453.26 K | 绛夌喌+鏁堢巼 |

---

## 4. 鍑犱綍涓庢嫇鎵?
- **灏侀棴寮?*锛歨ub disk 8.0 mm + shroud 2.0 mm + 12 鐗囧悗寮彾鐗囷紝鏋勬垚灏侀棴娴侀亾锛坰hr oud 涓?hub 鍚屾椂灏侀棴鍙堕亾锛岄潪鍗婂紑寮忥級銆?- **鍙堕亾**锛氳繘鍙?D1t 166.03 / D1h 76.5锛屽嚭鍙?D2 220 / b2 19.8锛岃酱鍚戦暱 82.5 mm銆?- **鍚庡集**锛毼?b = 25掳锛屽睘涓瓑鍚庡集锛屽吋椤惧帇姣斾笌绋冲畾宸ヤ綔鍩燂紙鈭抎P/dm 鏂滅巼閫備腑锛夈€?- **鍙埗閫犵害鏉?*锛氬彾鐗囧帤 1.8 鈮?1.2锛岃疆鐩栧帤 2.0 鈮?1.5锛屽彾鏍瑰渾瑙?1.2 鈮?1.0锛屽叏閮ㄦ弧瓒冲鏉?绮惧瘑閾搁€犱笅闄愩€?
---

## 5. 鏉愭枡涓庡己搴?
Ti-6Al-4V锛毾?4430 kg/m鲁锛屜僟y 880 MPa锛屛?0.34銆?鍙惰疆鐩樼瓑鏁堢幆鐩樺簲鍔?478.31 MPa 鈫?FOS 1.84锛屾弧瓒?鈮?1.5銆?**娉ㄦ剰 搂7 鐨?bore 鍒嗗眰椋庨櫓銆?*

---

## 6. 鍒嗚处锛堝繀椤讳笌缁撹鍚屾椂闃呰锛?
| 鐜妭 | 褰掑睘 |
|---|---|
| `Z_blades` / `beta2b_deg` / `eta_total` / `b2_ratio` / `D2` 棣栭€?/ `N` 棣栭€?| 妯″瀷锛坄virtu-ties-v1`锛?|
| `axial_length_mm` | 姹傝В鍣細鍙?[0.20路D2, 0.55路D2] 涓?L 鈮?th+ts+b2 鐨勫彲琛屽尯闂翠腑鍊?|
| `D1t_mm` / `D1h_mm` | 姹傝В鍣細鐢?ca1 鐩爣鍙嶈В鍠夊彛闈㈢Н锛屽彇 M_rel 鈮?1.13 鍏佽鐨?D1t 涓婄晫锛屽弽瑙?D1h |
| `b2_mm` | 姹傝В鍣細姣斿€?脳 D2 |
| `bore` / 鐩樺帤 / 鍦嗚 / 鍙跺帤 | 姹傝В鍣ㄦ寜宸ヨ壓涓嬮檺鍙栧€?|
| `claimed_*` | 灏哄瓙澶嶇畻娲剧敓锛堥潪妯″瀷濉啓锛?|
| 鍚堟牸鍒ゅ畾 | 灏哄瓙鐙珛缁欏嚭锛屾眰瑙ｅ櫒涓嶅弬涓?|

**妯″瀷鐨勮嚜鐢卞害鍙栧€肩粡瀵圭収瀹為獙璇佸疄涓?prompt 绀轰緥澶嶈**锛堟浛鎹㈢ず渚嬪€煎悗杈撳嚭閫愬瓧璺熼殢锛岃 `ROUTE_APRIME_REPORT.md` 搂4锛夈€傚洜姝ゆ湰璁捐**涓嶈兘浣滀负妯″瀷鑷富璁捐鑳藉姏鐨勮瘉鎹?*锛屽彧鑳戒綔涓哄伐浣滃彴宸ョ▼浜や粯鐗┿€?
---

## 7. 鏈弧瓒崇殑 advisory锛堝昂瀛愮粰鍑轰絾涓嶅垽杩濊锛?
1. **杞瘋瀛?bore 搴斿姏 799.4 MPa锛孎OS_bore = 1.10 < 1.5**銆?   灏哄瓙鐨勪富鍒ゆ嵁鐢ㄧ瓑鏁堢幆鐩?+ 鍙剁墖绯绘暟锛宐ore 鍒嗗眰搴斿姏鍙綔 advisory銆傜湡瀹?tapered 杞瘋蹇呴』鍋?FEA 澶嶆牳锛涜嫢鎸夌瓑鍘氱幆鐩樼洿鎺ユ姇浜э紝**鍦?40300 rpm 涓嬪睘浜庡己搴︿笉瓒?*銆傝繖鏄湰璁捐鏈€闇€瑕佷汉宸ヤ粙鍏ョ殑涓€椤广€?2. Ns = 0.741锛坮ad/s 鍩猴級锛屽浜庣蹇冪骇鍏稿瀷鍖洪棿 0.4鈥?.2 鐨勪腑涓婇儴锛屽睘楂橀€熷皬娴侀噺璁捐锛岄渶鍏虫敞杞存壙涓庤浆瀛愬姩鍔涘锛堜竴闃朵复鐣岃浆閫熸湭璇勪及锛夈€?3. 灏哄瓙鏃?D2 缁濆涓婇檺鍒ゆ嵁锛?20 mm 鏄ā鍨嬭嚜鐢卞害鍋忓ソ涓庡帇姣斿弽瑙ｇ殑鍏卞悓缁撴灉锛屾湭鍋氫笌鏈哄專/绾ч棿甯冨眬鐨勫共娑夋牎鏍搞€?
---

## 8. 妯″瀷鑷富璺嚎鐨勫悓姝ョ粨鏋滐紙瀵圭収锛?
鍚屼竴妯″瀷銆佸悓涓€ BRIEF锛宍--mode full`锛堟ā鍨嬬嫭鍗犲叏閮?17 瀛楁鍐崇瓥锛夌 9 娆¤繍琛岋紝8 杞細

```
round 2  杩濊 4   D2=100      u2=52.36
round 3  杩濊 8   D2=22700    u2=11885.69
round 4  杩濊 7   D2=10       u2=5.24
round 6  杩濊 9   D1t=0.4
round 7  杩濊 10  D2=0.04
round 8  杩濊 10  D2=0.04  锛堝璇伙級
```

`best_n_viol=4`锛宍passed=False`锛屾姤鍛?`report_virtu-ties-v1_latest_20261109_224231.json`銆?閲忕骇鍒ゆ柇瀹屽叏宕╁锛圖2 鍦?100 / 22700 / 10 / 0.04 闂磋烦鍙橈級锛宍claimed_pressure_ratio` 鎭掑～ 4.0锛宍claimed_tip_speed` 濮嬬粓鐢辫嚜缁?D2/N 绠楀嚭浣嗕笌鍘嬫瘮闇€姹傛棤鍏炽€?姝ょ粨鏋滀笌鏃㈡湁 8 娆″叏 FAIL銆乣LAYER1_ABLATION_REPORT` 鐨勪笁鑷傛秷铻嶄竴鑷达細缂洪櫡鍦ㄦ潈閲嶅眰鐨勯噺绾ч敋瀹氫笌璺ㄦ涓€鑷存€с€?
---

## 9. 澶嶇幇

```powershell
Set-Location "D:\Virtu妯″瀷"
.\.venv\Scripts\python.exe scripts\impeller_design_workbench.py --mode auto --model "virtu-ties-v1:latest" --host http://127.0.0.1:11435
```

*（内容由AI生成，仅供参考）*
