import re
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import ezdxf
import streamlit as st
import streamlit.components.v1 as components

DEFAULT_DXF = Path("examples/dxf_files/building005-0_floor2.dxf")

st.set_page_config(page_title="AI CAD Editor", layout="wide")
st.title("AI CAD Editor")


@st.cache_data(show_spinner=False)
def render_dxf_svg(path: str) -> str:
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.layout import Page
    from ezdxf.addons.drawing.svg import SVGBackend

    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    backend = SVGBackend()
    ctx = RenderContext(doc)
    Frontend(ctx, backend).draw_layout(msp)
    backend.finalize()
    page = Page(800, 500)
    svg_element = backend.get_xml_root_element(page)
    return ET.tostring(svg_element, encoding="unicode")


def show_dxf(path: str, label: str):
    st.caption(label)
    with st.spinner(f"Rendering {label}..."):
        svg = render_dxf_svg(path)
    svg = re.sub(r'\s+width="[^"]*"', '', svg, count=1)
    svg = re.sub(r'\s+height="[^"]*"', '', svg, count=1)
    svg = svg.replace('<svg ', '<svg style="width:100%;height:auto;display:block;" ', 1)
    html = (
        '<div style="width:100%;background:#1a1a1a;border-radius:8px;'
        'padding:8px;box-sizing:border-box;">'
        + svg + '</div>'
    )
    components.html(html, height=520, scrolling=False)


with st.sidebar:
    st.header("Settings")
    provider = st.selectbox("AI Provider", ["OpenAI (gpt-4o)", "Gemini (gemini-2.5-flash)"])

uploaded = st.file_uploader("Upload a DXF file", type=["dxf"])

if uploaded:
    if st.session_state.get("uploaded_name") != uploaded.name:
        tmp_dir = Path(tempfile.mkdtemp())
        dxf_path = tmp_dir / uploaded.name
        dxf_path.write_bytes(uploaded.read())
        st.session_state.uploaded_path = str(dxf_path)
        st.session_state.uploaded_name = uploaded.name
    dxf_path = Path(st.session_state.uploaded_path)
else:
    dxf_path = DEFAULT_DXF
    st.session_state.pop("uploaded_path", None)
    st.session_state.pop("uploaded_name", None)

agent_key = f"{dxf_path}|{provider}"
if "agent" not in st.session_state or st.session_state.get("agent_key") != agent_key:
    with st.spinner("Loading DXF..."):
        if "OpenAI" in provider:
            from ai_cad_editor.agent.cad_agent_openai import CADAgentOpenAI
            api_key = st.secrets.get("OPENAI_API_KEY") or None
            st.session_state.agent = CADAgentOpenAI(dxf_path, api_key=api_key)
        else:
            from ai_cad_editor.agent.cad_agent_gemini import CADAgentGemini
            api_key = st.secrets.get("GEMINI_API_KEY") or None
            st.session_state.agent = CADAgentGemini(dxf_path, api_key=api_key)
        st.session_state.agent_key = agent_key
        st.session_state.messages = []

st.caption(f"Loaded: **{dxf_path.name}** — {provider}")

agent = st.session_state.agent
modified_path = agent.last_output_path

col1, col2 = st.columns(2)
with col1:
    st.subheader("Before")
    show_dxf(str(dxf_path), dxf_path.name)
with col2:
    st.subheader("After")
    if modified_path and Path(modified_path).exists():
        show_dxf(modified_path, Path(modified_path).name)
        st.download_button(
            "Download modified DXF",
            data=Path(modified_path).read_bytes(),
            file_name=Path(modified_path).name,
            mime="application/octet-stream",
        )
    else:
        st.info("Make a change to see the result here.")

st.divider()

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

if prompt := st.chat_input("Ask something or give a command..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    with st.spinner("Thinking..."):
        try:
            response = agent.chat(prompt)
        except Exception as e:
            response = f"Error: {e}"

    st.session_state.messages.append({"role": "assistant", "content": response})
    st.chat_message("assistant").write(response)
    st.rerun()
