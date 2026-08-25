import streamlit as st
import pandas as pd
import numpy as np
import re
import io
import os
from pypdf import PdfReader

# ตั้งค่าหน้าเว็บ
st.set_page_config(
    page_title="TKK ERP - ระบบจัดการสินค้าและคลัง",
    page_icon="📦",
    layout="wide"
)

# ซ่อนปุ่มกากบาทของตัวอัปโหลดไฟล์ด้วย CSS
st.markdown("""
<style>
button[aria-label="Delete"] {
    display: none !important;
}
div[data-testid="stFileUploaderDeleteBtn"] {
    display: none !important;
}
</style>
""", unsafe_allow_html=True)

DB_FILE = "database_inventory.csv"

# รายการโซนทั้งหมด 30 โซน
ALL_ZONES = [
    "AA", "AB", "BB", "CC", "DD", "EE", "FF", "GG", "HH",
    "IA", "IB", "IC", "II", "JJ", "KK", "LL", "MA", "MB", 
    "MC", "MM", "NN", "OO", "PP", "QQ", "RR", "ST", "TT", 
    "UU", "XX", "YY"
]

# ==========================================
# 1. ฟังก์ชันจัดการฐานข้อมูลและการประมวลผล
# ==========================================
def load_database():
    if os.path.exists(DB_FILE):
        try:
            return pd.read_csv(DB_FILE, dtype=str)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

def save_database(df):
    df.to_csv(DB_FILE, index=False)

def format_tag_value(val):
    s = str(val).strip()
    if not s or s.lower() in ["nan", "none", "-", ""]:
        return "{ทั่วไป}"
    if s.startswith("{") and s.endswith("}"):
        return s
    m = re.search(r'[\{\[\(](.*?)[\}\]\)]', s)
    if m:
        return f"{{{m.group(1).strip()}}}"
    return f"{{{s}}}"

def parse_tag_and_clean_name(raw_text):
    text = str(raw_text).replace("•", "").strip()
    m_curly = re.search(r'\{([^}]+)\}', text)
    if m_curly:
        return f"{{{m_curly.group(1).strip()}}}", re.sub(r'\{[^}]+\}', '', text).strip()
    
    m_square = re.search(r'\[([^\]]+)\]', text)
    if m_square:
        return f"{{{m_square.group(1).strip()}}}", re.sub(r'\[[^\]]+\]', '', text).strip()

    m_paren = re.search(r'\(([^)]+)\)', text)
    if m_paren and len(m_paren.group(1).strip()) <= 15:
        return f"{{{m_paren.group(1).strip()}}}", re.sub(r'\([^)]+\)', '', text).strip()

    m_pipe = re.search(r'\|([^\|]+)\|', text)
    if m_pipe:
        return f"{{{m_pipe.group(1).strip()}}}", re.sub(r'\|[^\|]+\|', '', text).strip()
        
    return "{ทั่วไป}", text

def extract_fields_from_text(text, source_name, target_zone):
    pattern = re.compile(
        r'(\d{4,5})\s+รหัส\s*:\s*(\d+)\s*รหัสรอง\s*:\s*(\d+)[•\s\-]*(.*?)(?:\{([^}]+)\})?\s*หน่วยนับ\s*:\s*([^คง]+)คงเหลือ\s*:\s*([\-\d\.]+)\s*(เลิกขาย|ขาย)?\s*(\d+)\s*โซน\s*:\s*([A-Za-z0-9]+)',
        re.DOTALL
    )
    matches = pattern.findall(text)
    data = []
    for m in matches:
        raw_name = m[3].strip()
        tag, clean_name = parse_tag_and_clean_name(raw_name)
        if m[4]:
            tag = f"{{{m[4].strip()}}}"
        barcode = str(m[1]).strip()
        data.append({
            "#": m[0],
            "รหัสสินค้า": barcode,
            "รหัสรอง": str(m[2]).strip(),
            "ชื่อรายการสินค้า": clean_name,
            "แท็ก {Tag}": tag,
            "หน่วยนับ": m[5].strip(),
            "จำนวนสั่งล่าสุด": str(int(m[8])) if m[8].isdigit() else "0",
            "โซน": str(target_zone).upper().strip(),
            "คงเหลือ": str(m[6]).strip() if m[6] else "0",
            "สถานะ": m[7] if m[7] else "พร้อมขาย",
            "ชื่อไฟล์ที่มา": source_name
        })
    return pd.DataFrame(data)

def clean_and_prepare_df(raw_df, source_name, target_zone):
    df = raw_df.copy()
    df.columns = [f"{c}_{i}" if list(df.columns).count(c) > 1 else c for i, c in enumerate(df.columns)]
    
    # กำหนดโซนให้อิงตามเป้าหมายที่เลือกอัปโหลดเสมอ
    df["โซน"] = str(target_zone).upper().strip()
        
    # รหัสสินค้า
    barcode_col = next((c for c in df.columns if any(k in str(c).lower() for k in ["รหัสสินค้า", "barcode", "บาร์โค้ด"]) or str(c).strip() == "รหัส"), None)
    if barcode_col:
        df["รหัสสินค้า"] = df[barcode_col].astype(str).str.replace(":", "", regex=False).str.replace(r'\.0$', '', regex=True).str.strip()
    elif len(df.columns) > 2:
        df["รหัสสินค้า"] = df.iloc[:, 2].astype(str).str.replace(":", "", regex=False).str.replace(r'\.0$', '', regex=True).str.strip()

    # รหัสรอง
    sub_col = next((c for c in df.columns if any(k in str(c).lower() for k in ["รหัสรอง", "item_code"])), None)
    if sub_col:
        df["รหัสรอง"] = df[sub_col].astype(str).str.replace(":", "", regex=False).str.replace(r'\.0$', '', regex=True).str.strip()
    elif len(df.columns) > 3:
        df["รหัสรอง"] = df.iloc[:, 3].astype(str).str.replace(":", "", regex=False).str.replace(r'\.0$', '', regex=True).str.strip()

    # ยอดคงเหลือ
    stock_col = next((c for c in df.columns if "คงเหลือ" in str(c)), None)
    if stock_col:
        df["คงเหลือ"] = df[stock_col].astype(str).str.replace(":", "", regex=False).str.strip()
    elif len(df.columns) > 1:
        df["คงเหลือ"] = df.iloc[:, 1].astype(str).str.replace(":", "", regex=False).str.strip()

    # แท็กและชื่อสินค้า
    tag_col = next((c for c in df.columns if "แท็ก" in str(c) or "tag" in str(c).lower()), None)
    name_col = next((c for c in df.columns if any(k in str(c) for k in ["ชื่อ", "รายละ", "ยศ", "รายการ"])), None)
    if name_col is None and len(df.columns) > 4:
        name_col = df.columns[4]

    if tag_col:
        df["แท็ก {Tag}"] = df[tag_col].apply(format_tag_value)
        if name_col:
            df["ชื่อรายการสินค้า"] = df[name_col].astype(str).str.replace("•", "", regex=False).str.strip()
        else:
            df["ชื่อรายการสินค้า"] = "-"
    elif name_col:
        parsed = df[name_col].astype(str).apply(parse_tag_and_clean_name)
        df["แท็ก {Tag}"] = [p[0] for p in parsed]
        df["ชื่อรายการสินค้า"] = [p[1] for p in parsed]
    else:
        df["แท็ก {Tag}"] = "{ทั่วไป}"
        df["ชื่อรายการสินค้า"] = "-"

    if "จำนวนสั่งล่าสุด" not in df.columns:
        df["จำนวนสั่งล่าสุด"] = "0"
    if "สถานะ" not in df.columns:
        df["สถานะ"] = "พร้อมขาย"
    if "หน่วยนับ" not in df.columns:
        df["หน่วยนับ"] = "-"
        
    df["ชื่อไฟล์ที่มา"] = str(source_name)
    standard_cols = ["รหัสสินค้า", "รหัสรอง", "ชื่อรายการสินค้า", "แท็ก {Tag}", "หน่วยนับ", "จำนวนสั่งล่าสุด", "โซน", "คงเหลือ", "สถานะ", "ชื่อไฟล์ที่มา"]
    existing_cols = [c for c in standard_cols if c in df.columns]
    return df[existing_cols]

def parse_numeric_stock(val):
    try:
        s = str(val).strip().replace(":", "")
        return float(s)
    except Exception:
        return 0.0

def render_product_cards(items_df, current_zone, is_problem=False):
    cols = st.columns(3)
    for idx, row in items_df.iterrows():
        barcode = str(row.get("รหัสสินค้า", "")).strip()
        sub_code = str(row.get("รหัสรอง", "")).strip()
        name = str(row.get("ชื่อรายการสินค้า", "")).strip()
        qty = row.get("จำนวนสั่งล่าสุด", 0)
        stock = row.get("คงเหลือ", 0)
        
        img_url = f"https://tkkonlineshop.com/images/products/{barcode}.jpg"
        web_link = f"https://tkkonlineshop.com/products/{barcode}"
        
        with cols[idx % 3]:
            with st.container(border=True):
                st.image(
                    img_url, 
                    caption=f"รหัส: {barcode}", 
                    use_container_width=True
                )
                st.markdown(f"**{name}**")
                st.caption(f"รหัสสินค้า: `{barcode}` | โซน: `{current_zone}`")
                st.markdown(f"📋 **รหัสรอง (คลิกเพื่อ Copy):**")
                st.code(sub_code, language="text")
                if is_problem or parse_numeric_stock(stock) < 0:
                    st.markdown(f"🚨 **คงเหลือ:** :red[{stock}] | 🛒 **สั่งล่าสุด:** {qty}")
                else:
                    st.markdown(f"📦 **คงเหลือ:** {stock} | 🛒 **สั่งล่าสุด:** {qty}")
                st.link_button("🌐 เปิดดูบนเว็บ TKK Online", web_link, use_container_width=True)

# โหลดฐานข้อมูล
if "current_df" not in st.session_state:
    st.session_state.current_df = load_database()
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

# ==========================================
# 2. แถบเมนูด้านซ้าย (Sidebar)
# ==========================================
with st.sidebar:
    st.title("📦 TKK ERP Control")
    menu = st.radio(
        "🎯 เลือกฟังก์ชันการทำงาน",
        ["📊 ภาพรวมคลังสินค้า", "📑 จัดการสินค้า (รายโซน)", "⚠️ สินค้าที่มีปัญหา (คงเหลือติดลบ)", "🔍 ค้นหาสินค้า & Tag"]
    )
    
    st.divider()
    st.header("📍 โซนสินค้า (30 โซน)")
    selected_zone = st.selectbox("เลือกโซนที่ต้องการเข้าดู:", options=ALL_ZONES, index=0)
    
    st.divider()
    st.subheader(f"⚙️ การจัดการข้อมูล [โซน {selected_zone}]")
    
    # เพิ่มไฟล์ข้อมูลเข้าโซน
    with st.expander(f"📥 เพิ่มไฟล์ข้อมูลเข้าโซน {selected_zone}", expanded=False):
        uploaded_files = st.file_uploader(
            f"เลือกไฟล์สำหรับโซน {selected_zone} (PDF, CSV, XLSX)", 
            type=["pdf", "csv", "xlsx", "xls"], 
            accept_multiple_files=True,
            key=f"uploader_{selected_zone}_{st.session_state.uploader_key}"
        )
        
        if uploaded_files:
            preview_dfs = []
            for u_file in uploaded_files:
                try:
                    if u_file.name.endswith(".pdf"):
                        reader = PdfReader(u_file)
                        full_text = "".join([page.extract_text() + "\n" for page in reader.pages])
                        t_df = extract_fields_from_text(full_text, u_file.name, selected_zone)
                    elif u_file.name.endswith(".csv"):
                        t_df = clean_and_prepare_df(pd.read_csv(u_file), u_file.name, selected_zone)
                    elif u_file.name.endswith(".xlsx") or u_file.name.endswith(".xls"):
                        t_df = clean_and_prepare_df(pd.read_excel(u_file), u_file.name, selected_zone)
                    
                    if not t_df.empty:
                        t_df["โซน"] = str(selected_zone).upper().strip()
                        preview_dfs.append(t_df)
                except Exception as e:
                    st.error(f"ไฟล์ {u_file.name} ผิดพลาด: {e}")
            
            if preview_dfs:
                combined_new_df = pd.concat(preview_dfs, ignore_index=True)
                st.info(f"เตรียมพร้อมบันทึก: {len(combined_new_df)} รายการ เข้าโซน {selected_zone}")
                
                if st.button(f"💾 ยืนยันบันทึกเข้าโซน {selected_zone}", type="primary"):
                    if st.session_state.current_df.empty:
                        st.session_state.current_df = combined_new_df
                    else:
                        st.session_state.current_df = pd.concat([st.session_state.current_df, combined_new_df], ignore_index=True)
                        if "รหัสสินค้า" in st.session_state.current_df.columns and "โซน" in st.session_state.current_df.columns:
                            st.session_state.current_df.drop_duplicates(subset=["รหัสสินค้า", "โซน"], keep="last", inplace=True)
                    
                    save_database(st.session_state.current_df)
                    st.session_state.uploader_key += 1
                    st.success(f"✅ บันทึกข้อมูลเข้าโซน {selected_zone} เรียบร้อย!")
                    st.rerun()

    # ลบไฟล์ออกจากโซน
    with st.expander(f"📁 ลบข้อมูลไฟล์ในโซน {selected_zone}", expanded=False):
        df_all = st.session_state.current_df
        if not df_all.empty and "โซน" in df_all.columns and "ชื่อไฟล์ที่มา" in df_all.columns:
            zone_files = df_all[df_all["โซน"].astype(str).str.upper().str.strip() == str(selected_zone).upper().strip()]["ชื่อไฟล์ที่มา"].dropna().unique().tolist()
            if zone_files:
                selected_remove_file = st.selectbox("เลือกไฟล์ที่ต้องการลบ:", options=zone_files)
                if st.button("🗑️ ยืนยันลบไฟล์นี้"):
                    condition = (st.session_state.current_df["ชื่อไฟล์ที่มา"] == selected_remove_file) & (st.session_state.current_df["โซน"].astype(str).str.upper().str.strip() == str(selected_zone).upper().strip())
                    st.session_state.current_df = st.session_state.current_df[~condition]
                    save_database(st.session_state.current_df)
                    st.success(f"ลบข้อมูลสำเร็จ")
                    st.rerun()
            else:
                st.caption(f"ยังไม่มีไฟล์ข้อมูลในโซน {selected_zone}")
        else:
            st.caption("ยังไม่มีข้อมูลในระบบ")

# ==========================================
# 3. หน้าจอการทำงานหลัก (กรองเฉพาะโซนที่เลือก)
# ==========================================
df_all = st.session_state.current_df

# กรองอ่านค่าเฉพาะโซนที่เลือกเท่านั้น
if not df_all.empty and "โซน" in df_all.columns:
    df_zone = df_all[df_all["โซน"].astype(str).str.upper().str.strip() == str(selected_zone).upper().strip()].reset_index(drop=True)
else:
    df_zone = pd.DataFrame()

# ------------------------------------------
# ฟังก์ชัน 1: ภาพรวมคลังสินค้า
# ------------------------------------------
if menu == "📊 ภาพรวมคลังสินค้า":
    st.title("📊 ภาพรวมคลังสินค้า TKK ERP")
    
    if not df_all.empty:
        stock_nums = df_all["คงเหลือ"].apply(parse_numeric_stock) if "คงเหลือ" in df_all.columns else pd.Series([0]*len(df_all))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📦 รายการสินค้าทั้งหมด", f"{len(df_all):,} รายการ")
        c2.metric("✅ สินค้าพร้อมขาย", f"{len(df_all[df_all['สถานะ'].astype(str).str.contains('พร้อมขาย|ปกติ|ขาย', na=False)]):,} รายการ")
        c3.metric("⛔ สินค้าเลิกขาย", f"{len(df_all[df_all['สถานะ'].astype(str).str.contains('เลิกขาย', na=False)]):,} รายการ")
        c4.metric("⚠️ สต็อกติดลบ", f"{len(df_all[stock_nums < 0]):,} รายการ")

        st.markdown("---")
        st.subheader("📋 ตารางข้อมูลสินค้าทั้งหมดในระบบ (30 โซน)")
        display_all_df = df_all.drop(columns=["ชื่อไฟล์ที่มา"], errors="ignore")
        st.dataframe(display_all_df, use_container_width=True)

        csv_data = display_all_df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="📥 ดาวน์โหลดข้อมูลทั้งหมด (Cleaned CSV)",
            data=csv_data,
            file_name="TKKERP_Cleaned_All.csv",
            mime="text/csv"
        )
    else:
        st.info("💡 ยังไม่มีข้อมูลสินค้าในระบบ กรุณาเลือกโซนและอัปโหลดไฟล์ที่แถบเมนูด้านซ้าย")

# ------------------------------------------
# ฟังก์ชัน 2: จัดการสินค้า (รายโซน - เฉพาะโซนที่ติ๊กเลือก)
# ------------------------------------------
elif menu == "📑 จัดการสินค้า (รายโซน)":
    st.title(f"📑 ระบบจัดการสินค้าประจำโซน : {selected_zone}")

    if not df_zone.empty:
        col_t, col_s, col_v = st.columns([1.5, 2, 1.2])
        
        with col_t:
            tag_list = sorted(list(df_zone["แท็ก {Tag}"].dropna().unique())) if "แท็ก {Tag}" in df_zone.columns else []
            tag_options = ["📌 รวมทุกแท็ก (จัดกลุ่มตามแท็กอัตโนมัติ)"] + tag_list
            selected_tag = st.selectbox("🏷️ เลือกแท็กสินค้า:", options=tag_options)

        with col_s:
            stock_ranges = [
                "ทั้งหมด", "-1000 ถึง 0", "1-10", "10-20",
                "20-30", "30-40", "40-50", "50-100", "100-200"
            ]
            selected_range = st.select_slider("🔢 เลือกช่วงจำนวนสต็อกคงเหลือ:", options=stock_ranges, value="ทั้งหมด")
        
        with col_v:
            display_type = st.radio("รูปแบบการแสดงผล:", ["🖼️ รูปภาพสินค้า (Cards)", "📋 ตารางข้อมูล (Table)"], horizontal=True)

        # กรองเฉพาะแท็กภายในโซนที่เลือก
        if selected_tag == "📌 รวมทุกแท็ก (จัดกลุ่มตามแท็กอัตโนมัติ)":
            base_df = df_zone.copy()
        else:
            base_df = df_zone[df_zone["แท็ก {Tag}"] == selected_tag].copy()

        # กรองตามช่วงสต็อก
        numeric_stocks = base_df["คงเหลือ"].apply(parse_numeric_stock)

        if selected_range == "-1000 ถึง 0":
            mask = (numeric_stocks >= -1000) & (numeric_stocks <= 0)
            filtered_df = base_df[mask].copy()
            filtered_df["_sort_num"] = filtered_df["คงเหลือ"].apply(parse_numeric_stock)
            filtered_df = filtered_df.sort_values(by="_sort_num", ascending=True).drop(columns=["_sort_num"])
        elif selected_range == "1-10":
            filtered_df = base_df[(numeric_stocks >= 1) & (numeric_stocks <= 10)]
        elif selected_range == "10-20":
            filtered_df = base_df[(numeric_stocks > 10) & (numeric_stocks <= 20)]
        elif selected_range == "20-30":
            filtered_df = base_df[(numeric_stocks > 20) & (numeric_stocks <= 30)]
        elif selected_range == "30-40":
            filtered_df = base_df[(numeric_stocks > 30) & (numeric_stocks <= 40)]
        elif selected_range == "40-50":
            filtered_df = base_df[(numeric_stocks > 40) & (numeric_stocks <= 50)]
        elif selected_range == "50-100":
            filtered_df = base_df[(numeric_stocks > 50) & (numeric_stocks <= 100)]
        elif selected_range == "100-200":
            filtered_df = base_df[(numeric_stocks > 100) & (numeric_stocks <= 200)]
        else:
            filtered_df = base_df.copy()

        filtered_df = filtered_df.reset_index(drop=True)

        st.markdown("---")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📍 โซนที่เลือก", f"โซน {selected_zone}")
        m2.metric("🏷️ แท็กที่เลือก", "รวมทุกแท็ก" if selected_tag == "📌 รวมทุกแท็ก (จัดกลุ่มตามแท็กอัตโนมัติ)" else selected_tag)
        m3.metric("🎯 เงื่อนไขสต็อก", selected_range)
        m4.metric("📦 พบสินค้า", f"{len(filtered_df):,} รายการ")

        if not filtered_df.empty:
            if display_type == "🖼️ รูปภาพสินค้า (Cards)":
                if selected_tag == "📌 รวมทุกแท็ก (จัดกลุ่มตามแท็กอัตโนมัติ)":
                    present_tags = sorted(list(filtered_df["แท็ก {Tag}"].dropna().unique()))
                    for tag in present_tags:
                        group_df = filtered_df[filtered_df["แท็ก {Tag}"] == tag].reset_index(drop=True)
                        with st.expander(f"📦 แท็ก: **{tag}** (พบ {len(group_df)} รายการ)", expanded=True):
                            render_product_cards(group_df, selected_zone)
                else:
                    render_product_cards(filtered_df, selected_zone)
            else:
                def highlight_neg(val):
                    try:
                        num = float(str(val).replace(":", ""))
                        if num < 0:
                            return "background-color: #ffebee; color: #c62828; font-weight: bold;"
                        elif num == 0:
                            return "background-color: #fffde7; color: #f57f17; font-weight: bold;"
                        return ""
                    except Exception:
                        return ""

                try:
                    styled_df = filtered_df.drop(columns=["ชื่อไฟล์ที่มา"], errors="ignore").style.map(highlight_neg, subset=["คงเหลือ"])
                except AttributeError:
                    styled_df = filtered_df.drop(columns=["ชื่อไฟล์ที่มา"], errors="ignore").style.applymap(highlight_neg, subset=["คงเหลือ"])

                st.dataframe(styled_df, use_container_width=True)

            st.divider()
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                filtered_df.drop(columns=["ชื่อไฟล์ที่มา"], errors="ignore").to_excel(writer, sheet_name=f"โซน_{selected_zone}", index=False)
            
            st.download_button(
                label=f"📥 ดาวน์โหลดไฟล์ Excel โซน {selected_zone} (.xlsx)",
                data=output.getvalue(),
                file_name=f"ข้อมูลสินค้า_โซน_{selected_zone}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning(f"ℹ️ ไม่พบรายการสินค้าในโซน {selected_zone} สำหรับแท็ก '{selected_tag}' ที่ตรงกับเงื่อนไขสต็อก '{selected_range}'")
    else:
        st.info(f"👈 โซน **{selected_zone}** ยังไม่มีข้อมูลสินค้า คลิกที่เมนูด้านซ้าย **'📥 เพิ่มไฟล์ข้อมูลเข้าโซน {selected_zone}'** เพื่ออัปโหลด")

# ------------------------------------------
# ฟังก์ชัน 3: สินค้าที่มีปัญหา (เฉพาะโซนที่ติ๊กเลือก)
# ------------------------------------------
elif menu == "⚠️ สินค้าที่มีปัญหา (คงเหลือติดลบ)":
    st.title(f"⚠️ สินค้าที่มีปัญหา [คงเหลือติดลบ -] : โซน {selected_zone}")
    
    if not df_zone.empty and "คงเหลือ" in df_zone.columns:
        numeric_stocks = df_zone["คงเหลือ"].apply(parse_numeric_stock)
        problem_df = df_zone[numeric_stocks < 0].copy()
        
        problem_df["_sort_num"] = problem_df["คงเหลือ"].apply(parse_numeric_stock)
        problem_df = problem_df.sort_values(by="_sort_num", ascending=True).drop(columns=["_sort_num"]).reset_index(drop=True)
        
        if not problem_df.empty:
            st.error(f"🚨 พบสินค้าคงเหลือติดลบทั้งหมด **{len(problem_df)} รายการ** ในโซน {selected_zone}")
            
            prob_tags = sorted(list(problem_df["แท็ก {Tag}"].dropna().unique()))
            tag_options = ["📌 รวมทุกแท็ก (จัดกลุ่มตามแท็กอัตโนมัติ)"] + prob_tags
            selected_prob_tag = st.selectbox("🏷️ เลือกกลุ่มแท็กสินค้าที่มีปัญหา:", options=tag_options)
            
            if selected_prob_tag == "📌 รวมทุกแท็ก (จัดกลุ่มตามแท็กอัตโนมัติ)":
                for tag in prob_tags:
                    group_prob_df = problem_df[problem_df["แท็ก {Tag}"] == tag].reset_index(drop=True)
                    with st.expander(f"🚨 แท็ก: **{tag}** (รวม {len(group_prob_df)} รายการ)", expanded=True):
                        render_product_cards(group_prob_df, selected_zone, is_problem=True)
            else:
                filtered_prob_df = problem_df[problem_df["แท็ก {Tag}"] == selected_prob_tag].reset_index(drop=True)
                st.write(f"พบ **{len(filtered_prob_df)} รายการ** ที่ติดลบ ในแท็ก `{selected_prob_tag}`")
                render_product_cards(filtered_prob_df, selected_zone, is_problem=True)

            st.divider()
            st.subheader(f"📋 ตารางรายการสินค้าที่มีปัญหา [โซน {selected_zone}]")
            display_prob_df = problem_df.drop(columns=["ชื่อไฟล์ที่มา"], errors="ignore")
            st.dataframe(display_prob_df, use_container_width=True)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                display_prob_df.to_excel(writer, sheet_name=f"ปัญหา_{selected_zone}", index=False)
            
            st.download_button(
                label=f"📥 ดาวน์โหลดรายการสินค้ามีปัญหา โซน {selected_zone} (.xlsx)",
                data=output.getvalue(),
                file_name=f"สินค้ามีปัญหา_โซน_{selected_zone}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.success(f"🎉 ยอดเยี่ยม! ไม่พบสินค้าคงเหลือติดลบในโซน {selected_zone}")
    else:
        st.info(f"👈 โซน {selected_zone} ยังไม่มีข้อมูลสินค้า")

# ------------------------------------------
# ฟังก์ชัน 4: ค้นหาสินค้า & Tag
# ------------------------------------------
elif menu == "🔍 ค้นหาสินค้า & Tag":
    st.title("🔍 ค้นหาและจัดกลุ่มสินค้าตาม Tag / รหัส")

    search_kw = st.text_input("🔎 ค้นหาด้วย ชื่อสินค้า / บาร์โค้ด / รหัสรอง / Tag / โซน:", "")

    if search_kw and not df_all.empty:
        mask = (
            df_all["ชื่อรายการสินค้า"].astype(str).str.contains(search_kw, case=False, na=False)
            | df_all["รหัสสินค้า"].astype(str).str.contains(search_kw, case=False, na=False)
            | df_all["รหัสรอง"].astype(str).str.contains(search_kw, case=False, na=False)
            | df_all["แท็ก {Tag}"].astype(str).str.contains(search_kw, case=False, na=False)
            | df_all["โซน"].astype(str).str.contains(search_kw, case=False, na=False)
        )
        res_df = df_all[mask].reset_index(drop=True)
        st.write(f"ผลการค้นหา: พบ **{len(res_df)}** รายการ")
        
        view_res_type = st.radio("เลือกมุมมองผลการค้นหา:", ["🖼️ แสดงรูปภาพ (Cards)", "📋 ตารางข้อมูล (Table)"], horizontal=True)
        if view_res_type == "🖼️ แสดงรูปภาพ (Cards)":
            render_product_cards(res_df, "หลายโซน")
        else:
            st.dataframe(res_df.drop(columns=["ชื่อไฟล์ที่มา"], errors="ignore"), use_container_width=True)
    elif not search_kw:
        st.info("💡 พิมพ์คำค้นหา เช่น ชื่อสินค้า, แท็ก `{PV}`, หรือรหัสบาร์โค้ด เพื่อค้นหาด่วนจากทุกโซน")
    else:
        st.warning("⚠️ ยังไม่มีข้อมูลในระบบ กรุณาอัปโหลดไฟล์ข้อมูลก่อนทำการค้นหา")
