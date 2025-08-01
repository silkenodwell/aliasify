import re
import itertools
import collections
import json
import pandas as pd
import streamlit as st

# -----------------------------------------------------------------------------
# ⚙️  spaCy model loader (auto‑downloads en_core_web_sm if missing)
# -----------------------------------------------------------------------------
@st.cache_resource(show_spinner="Loading spaCy model…")
def get_nlp():
    try:
        import spacy
        return spacy.load("en_core_web_sm")
    except OSError:
        import spacy, spacy.cli
        with st.spinner("Downloading spaCy model (~15 MB)…"):
            spacy.cli.download("en_core_web_sm")
        return spacy.load("en_core_web_sm")

nlp = get_nlp()

# -----------------------------------------------------------------------------
# 🅰️  Alias generation helpers
# -----------------------------------------------------------------------------
_PREFIX = {
    "PERSON": "Pers",
    "ORG": "Org",
    "GPE": "Loc",
    "LOC": "Loc",
    "PRODUCT": "Prod",
    "DATE": "Date",
    "TIME": "Time",
    "MONEY": "Mon",
}
_COUNTERS = collections.defaultdict(itertools.count)

def make_alias(label: str) -> str:
    idx = next(_COUNTERS[label])  # 0, 1, 2 … per label
    prefix = _PREFIX.get(label, label.title()[:4])
    suffix = chr(ord("A") + idx % 26) + (str(idx // 26) if idx >= 26 else "")
    return f"{prefix}_{suffix}"

# -----------------------------------------------------------------------------
# 🔄  Encode / Decode
# -----------------------------------------------------------------------------

def encode(text: str, mapping: dict[str, str]) -> str:
    if not mapping:
        return text
    keys_sorted = sorted(mapping, key=len, reverse=True)
    pattern = re.compile("(" + "|".join(map(re.escape, keys_sorted)) + ")")
    return pattern.sub(lambda m: mapping[m.group(0)], text)


def decode(text: str, mapping: dict[str, str]) -> str:
    reverse = {v: k for k, v in mapping.items()}
    if not reverse:
        return text
    keys_sorted = sorted(reverse, key=len, reverse=True)
    pattern = re.compile("(" + "|".join(map(re.escape, keys_sorted)) + ")")
    return pattern.sub(lambda m: reverse[m.group(0)], text)

# -----------------------------------------------------------------------------
# 🖼️  Streamlit UI
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Entity Privacy Wrapper", page_icon="🕵️‍♂️", layout="centered")
st.title("🕵️‍♂️ Entity Privacy Wrapper")
st.markdown(
    "Mask named entities in your text before sending it to an LLM, then restore "
    "them afterwards — all locally in your browser session."
)

# -- 1. Raw input --------------------------------------------------------------
raw_text = st.text_area("Paste your *original* text here", height=200, key="raw_text")

if st.button("🔍 Detect / Refresh Entities", key="detect_btn"):
    if not raw_text.strip():
        st.warning("Please enter some text first.")
    else:
        doc = nlp(raw_text)
        ents = [(ent.text, ent.label_) for ent in doc.ents]
        if not ents:
            st.info("No entities detected with the current model.")
        else:
            # Persist source text & entities in session_state
            st.session_state["raw_text_store"] = raw_text
            st.session_state["entities"] = ents
            # Build / update mapping deterministically
            mapping = st.session_state.get("mapping", {})
            for ent_text, ent_label in ents:
                mapping.setdefault(ent_text, make_alias(ent_label))
            st.session_state["mapping"] = mapping
            # Reset previous encode result
            st.session_state.pop("encoded_text", None)

# -- 2. Review & tweak mapping -------------------------------------------------
if "entities" in st.session_state and st.session_state["entities"]:
    ents = st.session_state["entities"]
    mapping = st.session_state["mapping"]

    rows = [
        {
            "Entity": ent_text,
            "Label": ent_label,
            "Alias": mapping[ent_text],
            "Include": True,
        }
        for ent_text, ent_label in ents
    ]
    df = pd.DataFrame(rows)

    st.markdown("### Confirm replacements")

    with st.form("mapping_form", clear_on_submit=False):
        edited_df = st.data_editor(
            df,
            num_rows="fixed",
            column_config={
                "Alias": st.column_config.TextColumn(width="medium"),
                "Include": st.column_config.CheckboxColumn(required=True),
            },
            key="mapping_editor",
        )
        submitted = st.form_submit_button("🔒 Encode")
        if submitted:
            active_map = {
                row.Entity: row.Alias
                for row in edited_df.itertuples()
                if row.Include
            }
            st.session_state["active_map"] = active_map
            st.session_state["encoded_text"] = encode(
                st.session_state["raw_text_store"], active_map
            )
            st.success("Text encoded. Scroll down to copy or decode.")

# -- 3. Show encoded text -------------------------------------------------------
if "encoded_text" in st.session_state:
    st.text_area(
        "Encoded text (copy & send to LLM)",
        value=st.session_state["encoded_text"],
        height=200,
    )
    st.code(
        "Mapping used:\n" + json.dumps(st.session_state["active_map"], indent=2),
        language="json",
    )

# -- 4. Decode helper ----------------------------------------------------------
st.divider()
encoded_reply = st.text_area("Paste the LLM's *encoded* reply here", height=200, key="encoded_reply")

if st.button("🔓 Decode", key="decode_btn"):
    active_map = st.session_state.get("active_map")
    if not active_map:
        st.warning("No active mapping found. Please encode some text first in this session.")
    else:
        decoded_text = decode(encoded_reply, active_map)
        st.text_area("Decoded reply", value=decoded_text, height=200)

# -- 5. Reset button ----------------------------------------------------------
if st.button("🔄 Reset", key="reset_btn"):
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.session_state["raw_text"] = ""
    st.session_state["encoded_reply"] = ""
    st.rerun()
