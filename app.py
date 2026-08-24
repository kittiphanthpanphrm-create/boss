import streamlit as st
import pandas as pd
import plotly.express as px
import re
import io
import requests
from pypdf import PdfReader

st.set_page_config(page_title="ระบบแยกคอลัมน์ & แดชบอร์ดสินค้า", layout="wide")
st.title("📦 ระบบจัดการและแดชบอร์ดข้อมูลสินค้า")
st.write("เลือกแท็กเพื่อดูรายการสินค้า รูปภาพจากร้านค้าออนไลน์ และคัดลอกรหัสรอง")

def extract_fields_from_text(text):
    pattern = re.compile(
        r'(\d{4,5})\s+รหัส\s*:\s*(\d+)\s*รหัสรอง\s*:\s*(\d+)[•\s\-]*(.*?)(?:\{([^}]+)\})?\s*หน่วยนับ\s*:\s*([^คง]+)คงเหลือ\s*:\s*([\-\d\.]+)\s*(เลิกขาย|ขาย)?\s*(\d+)\s*โซน\s*:\s*([A-Za-z0-9]+)',
        re.DOTALL
    )
    matches = pattern.findall(text)
    data = []
    for m in matches:
        raw_tag = m[4] if m[4] else ""
        data.append({
            "#": m[0],
            "รหัสสินค้า": str(m[1]).strip(),
            "รหัสรอง": str(m[2]).strip(),
            "ชื่อรายการสินค้า": m[3].strip(),
            "แท็ก {Tag}": f"{{{raw_tag}}}" if raw_tag else "-",
            "หน่วยนับ": m[5].strip(),
            "จำนวนสั่งล่าสุด": int(m[8]) if m[8].isdigit() else 0,
            "โซน": m[9].strip(),
            "คงเหลือ": float(m[6]) if m[6] else 0.0,
            "สถานะ": m[7] if m[7] else "ปกติ"
        })
    return pd.DataFrame(data)

def clean_and_prepare_df(raw_df):
    df = raw_df.copy()
    for col in df.columns:
        if "รหัสสินค้า" in col or col == "รหัส":
            df["รหัสสินค้า"] = df[col].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        if "รหัสรอง" in col:
            df["รหัสรอง"] = df[col].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            
    if "แท็ก {Tag}" not in df.columns:
        name_col = next((c for c in df.columns if "ชื่อ" in c or "รายละ" in c), df.columns[3] if len(df.columns) > 3 else df.columns[0])
        def get_tag(x):
            m = re.search(r'\{([^}]+)\}', str(x))
            return f"{{{m.group(1)}}}" if m else "-"
        def get_name(x):
            return re.sub(r'\{[^}]+\}', '', str(x)).strip()
            
        df["แท็ก {Tag}"] = df[name_col].apply(get_tag)
        df["ชื่อรายการสินค้า"] = df[name_col].apply(get_name)
    
    for c in df.columns:
        if "สั่ง" in c:
            df["จำนวนสั่งล่าสุด"] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        if "คงเหลือ" in c:
            df["คงเหลือ"] = pd.to_numeric(df[c], errors="coerce").fillna(0)
            
    return df

uploaded_file = st.file_uploader("📂 เลือกไฟล์ข้อมูล (PDF, CSV, XLSX)", type=["pdf", "csv", "xlsx"])

if uploaded_file is not None:
    try:
        if "loaded_file" not in st.session_state or st.session_state.loaded_file != uploaded_file.name:
            if uploaded_file.name.endswith(".pdf"):
                reader = PdfReader(uploaded_file)
                full_text = "".join([page.extract_text() + "\n" for page in reader.pages])
                init_df = extract_fields_from_text(full_text)
            elif uploaded_file.name.endswith(".csv"):
                init_df = clean_and_prepare_df(pd.read_csv(uploaded_file))
            elif uploaded_file.name.endswith(".xlsx"):
                init_df = clean_and_prepare_df(pd.read_excel(uploaded_file))
                
            st.session_state.df = init_df
            st.session_state.loaded_file = uploaded_file.name

        df = st.session_state.df

        if df is not None and not df.empty:
            st.success(f"ประมวลผลข้อมูลสำเร็จ พบทั้งหมด {len(df):,} รายการ")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("จำนวนรายการทั้งหมด", f"{len(df):,} รายการ")
            c2.metric("จำนวนแท็กกลุ่มสินค้า", f"{df['แท็ก {Tag}'].nunique():,} กลุ่ม")
            c3.metric("รวมยอดสั่งล่าสุด", f"{int(df.get('จำนวนสั่งล่าสุด', pd.Series([0])).sum()):,} ชิ้น")
            c4.metric("รวมสินค้าคงเหลือ", f"{int(df.get('คงเหลือ', pd.Series([0])).sum()):,} ชิ้น")

            st.divider()

            st.subheader("🖼️ แสดงสินค้าและรูปภาพตามกลุ่มแท็ก")
            tag_list = sorted(list(df["แท็ก {Tag}"].unique()))
            selected_tag = st.selectbox("🏷️ เลือกกลุ่มแท็กสินค้าที่ต้องการดู:", options=tag_list)
            
            if selected_tag:
                filtered_df = df[df["แท็ก {Tag}"] == selected_tag].reset_index(drop=True)
                st.write(f"พบ **{len(filtered_df)} รายการ** ในแท็ก `{selected_tag}`")
                
                cols = st.columns(3)
                for idx, row in filtered_df.iterrows():
                    barcode = str(row.get("รหัสสินค้า", "")).strip()
                    sub_code = str(row.get("รหัสรอง", "")).strip()
                    name = str(row.get("ชื่อรายการสินค้า", "")).strip()
                    qty = row.get("จำนวนสั่งล่าสุด", 0)
                    stock = row.get("คงเหลือ", 0)
                    
                    img_url = f"https://tkkonlineshop.com/images/products/{barcode}.jpg"
                    
                    with cols[idx % 3]:
                        with st.container(border=True):
                            st.image(
                                img_url, 
                                caption=f"รหัส: {barcode}", 
                                use_container_width=True
                            )
                            st.markdown(f"**{name}**")
                            st.caption(f"รหัสสินค้า: `{barcode}`")
                            st.markdown(f"📋 **รหัสรอง (คลิกที่กล่องเพื่อ Copy):**")
                            st.code(sub_code, language="text")
                            st.markdown(f"📦 **คงเหลือ:** {stock} | 🛒 **สั่งล่าสุด:** {qty}")

            st.divider()

            st.subheader("📋 ตารางรายการข้อมูลทั้งหมด")
            st.dataframe(df, use_container_width=True)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="ข้อมูลสินค้าเรียงแท็ก", index=False)
            
            st.download_button(
                label="📥 ดาวน์โหลดไฟล์เป็น Excel (.xlsx)",
                data=output.getvalue(),
                file_name="สรุปข้อมูลสินค้าแยกแท็ก.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาด: {e}")
