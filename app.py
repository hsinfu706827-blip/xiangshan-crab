import json
import os
import pandas as pd
import streamlit as st
from PIL import Image
from google import genai
from google.genai import types

# 1. 初始化 Gemini
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# 定義目標物種、分數與 AI 辨識特徵
TARGETS = {
    "弧邊招潮蟹 (Fiddler Crab - 1分)": {
        "points": 1,
        "hint": "雄蟹有一支巨大的橘紅色或橙黃色大螯，背甲深褐色帶網狀花紋。"
    },
    "清白招潮蟹 (Milky Fiddler Crab - 1分)": {
        "points": 1,
        "hint": "體型較小，全身與大螯皆為明顯的乳白色或淡灰色，無強烈黑白反差。"
    },
    "短指和尚蟹 (Soldier Crab - 2分)": {
        "points": 2,
        "hint": "圓球狀藍灰色小螃蟹，常成群結隊在沙泥地上活動。"
    },
    "萬歲大眼蟹 (Sentinel Crab - 2分)": {
        "points": 2,
        "hint": "眼柄非常細長，雙螯細長且常向上舉起。"
    },
    "台灣招潮蟹 (Taiwanese Fiddler Crab - 4分)": {
        "points": 4,
        "hint": "必須同時具備「深黑或深褐色背甲」與「寬扁修長如剪刀狀的白色大螯」（強烈黑白對比）。若全身偏白請判為不符（那是清白招潮蟹）。"
    },
    "彈塗魚 (Mudskipper - 2分)": {
        "points": 2,
        "hint": "兩棲魚類，有突出的雙眼與胸鰭，在泥灘上爬行或跳躍。"
    }
}

TEAMS = ["Team 1", "Team 2", "Team 3", "Team 4", "Team 5"]

# 2. 共用狀態：紀錄各組解鎖進度與過關照片
@st.cache_resource
def get_game_state():
    progress = {team: {sp: False for sp in TARGETS} for team in TEAMS}
    gallery = []  # 存放過關紀錄方便老師複查
    return {"progress": progress, "gallery": gallery}

state = get_game_state()
progress = state["progress"]
gallery = state["gallery"]

# 3. 頁面標題與即時集點表
st.set_page_config(page_title="Xiangshan Crab Blitz", page_icon="🦀", layout="centered")
st.title("🦀 香山濕地蟹蟹大搜查")
st.caption("Hallo Krabben! Select your team & target species to unlock points.")

st.subheader("🏆 各組解鎖進度與總分 Live Scoreboard")
board_data = []
for t in TEAMS:
    row = {"組別 Team": t}
    total = 0
    for sp, info in TARGETS.items():
        short_name = sp.split(" ")[0]
        if progress[t][sp]:
            row[short_name] = "✅"
            total += info["points"]
        else:
            row[short_name] = "⬜"
    row["總分 Pts"] = total
    board_data.append(row)

st.dataframe(pd.DataFrame(board_data), hide_index=True, use_container_width=True)

st.divider()

# 4. 學生任務上傳區（先選組別 -> 再選對應物種 -> 上傳照片）
st.subheader("📸 上傳照片解鎖物種 Upload & Verify")

col1, col2 = st.columns(2)
with col1:
    team = st.selectbox("1️⃣ 選擇組別 Select Team", TEAMS)

with col2:
    # 標示出該組哪些物種已經解鎖
    species_options = list(TARGETS.keys())
    target_species = st.selectbox(
        "2️⃣ 選擇要解鎖的目標物種 Target Species",
        species_options,
        format_func=lambda x: f"✅ {x} (已解鎖)" if progress[team][x] else f"⬜ {x}"
    )

if progress[team][target_species]:
    st.info(f"👍 {team} 已經解鎖過「{target_species.split(' ')[0]}」囉！請挑戰其他尚未解鎖的物種。")
else:
    uploaded_file = st.file_uploader(
        f"3️⃣ 上傳你找到的【{target_species.split(' ')[0]}】照片（記得角落比手勢！）",
        type=["jpg", "jpeg", "png"]
    )

    if uploaded_file and st.button("🚀 提交給 AI 裁判驗證 (Verify)", type="primary"):
        img = Image.open(uploaded_file)
        st.image(img, caption=f"{team} 挑戰項目：{target_species}", use_container_width=True)

        target_hint = TARGETS[target_species]["hint"]
        prompt = f"""
        你是新竹香山濕地生態競賽的雙語 AI 裁判。
        學生目前聲稱這張照片拍到的是：【{target_species}】。
        該物種的辨識特徵為：{target_hint}

        請嚴格檢驗這張照片並以 JSON 格式回傳結果（不要加 markdown 標記）：
        1. 照片中的生物是否真的是【{target_species}】？（考量學生在木棧道遠距離變焦拍攝，畫質可能略微模糊，若特徵相符請從寬認定；但若是明顯不同物種，例如拿清白招潮蟹冒充台灣招潮蟹，請判為 false）。
        2. 畫面角落是否有「人類手勢或號碼牌」（防作弊機制）？

        回傳格式：
        {{
          "is_match": true 或 false,
          "has_hand_sign": true 或 false,
          "feedback": "給學生的簡短中英文評語（說明為何通過，或為何不符／缺少手勢）"
        }}
        """

        with st.spinner("AI 裁判比對特徵中... Verifying..."):
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=[img, prompt],
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            result = json.loads(response.text)

        # 5. 判定過關並更新集點表
        if result["is_match"] and result["has_hand_sign"]:
            progress[team][target_species] = True
            pts = TARGETS[target_species]["points"]
            # 縮小圖片存入照片牆以節省記憶體
            thumb = img.copy()
            thumb.thumbnail((400, 400))
            gallery.insert(0, {
                "team": team,
                "species": target_species,
                "points": pts,
                "image": thumb,
                "feedback": result["feedback"]
            })
            st.success(f"🎉 驗證通過！{team} 成功解鎖【{target_species.split(' ')[0]}】（+{pts} 分）")
            st.balloons()
            st.info(f"🤖 AI 評語：{result['feedback']}")
            st.button("🔄 刷新上方計分板")
        elif result["is_match"] and not result["has_hand_sign"]:
            st.warning("😅 螃蟹找對了，但 AI 沒看到你們的「專屬手勢」！請重新拍一張有手勢的照片。")
            st.info(f"🤖 AI 評語：{result['feedback']}")
        else:
            st.error(f"❌ 驗證未通過：AI 認為這不是【{target_species.split(' ')[0]}】。")
            st.info(f"🤖 AI 評語：{result['feedback']}")

# 6. 戰利品照片牆（老師現場複查與講評用）
st.divider()
with st.expander(f"🖼️ 即時過關照片牆（目前共 {len(gallery)} 筆）", expanded=False):
    if not gallery:
        st.caption("目前還沒有組別解鎖物種，快去尋找第一隻螃蟹吧！")
    else:
        for item in gallery:
            st.markdown(f"**{item['team']}** 解鎖了 **{item['species']}**")
            st.image(item["image"], width=300)
            st.caption(item["feedback"])
            st.markdown("---")
