import re
import itertools
import collections
import pandas as pd
import streamlit as st

# -----------------------------------------------------------------------------
# ⚙️  Lazy‑load spaCy model (en_core_web_sm). Automatically downloads if absent.
# -----------------------------------------------------------------------------
@st.cache_resource(show_spinner="Loading spaCy model…")
def get_nlp():
    try:
        import spacy
        return spacy.load("en_core_web_sm")
    except OSError:
        import spacy.cli
        with st.spinner("Downloading spaCy model (~15 MB)…"):
            spacy.cli.download("en_core_web_sm")
        import spacy as _sp
        return _sp.load("en_core_web_sm")

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

def _make_alias(label: str) -> str:
    """Return a short, deterministic alias for a given entity label."""
    counters = st.session_state.setdefault("_alias_counters", collections.defaultdict(itertools.count))
    idx = next(counters[label])  # 0, 1, 2 … per label
    prefix = _PREFIX.get(label, label.title()[:4])
    # Letter suffix A–Z, then A0, A1… after 26
    suffix = chr(ord("A") + idx % 26)
    if idx >= 26:
        suffix += str(idx // 26)
    return f"{prefix}_{suffix}"

# -----------------------------------------------------------------------------
# 🔄  Encode / Decode
# -----------------------------------------------------------------------------

def _encode(text: str, mapping: dict[str, str]) -> str:
    """Replace every key in *mapping* with its value (strict, case‑sensitive)."""
    if not mapping:
        return text
    # To avoid partial overlaps, sort by length ↓ ("New York" before "New").
    keys_sorted = sorted(mapping, key=len, reverse=True)
    pattern = re.compile("(" + "|".join(map(re.escape, keys_sorted)) + ")")
    return pattern.sub(lambda m: mapping[m.group(0)], text)


def _decode(text: str, mapping: dict[str, str]) -> str:
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

if st.button("🔍 Detect entities", type="primary"):
    if not raw_text.strip():
        st.warning("Please enter some text first.")
        st.stop()

    doc = nlp(raw_text)
    entities = [(ent.text, ent.label_) for ent in doc.ents]

    if not entities:
        st.info("No entities detected with the current model.")
        st.stop()

    # Build / update mapping
    mapping = st.session_state.setdefault("mapping", {})
    for ent_text, ent_label in entities:
        mapping.setdefault(ent_text, _make_alias(ent_label))

    # ---------------------------------------------------------------------
    # 2. Review & tweak mapping (DataEditor is editable)
    # ---------------------------------------------------------------------
    df = pd.DataFrame([
        {"Entity": k, "Label": nlp.vocab.strings[lbl] if isinstance(lbl, int) else lbl,
         "Alias": v, "Include": True}
        for k, v in mapping.items()
        for lbl in [next((l for t, l in entities if t == k), "-")]
    ])

    st.markdown("### Confirm replacements")
    edited_df = st.data_editor(
        df,
        num_rows="fixed",
        column_config={
            "Alias": st.column_config.TextColumn(width="medium"),
            "Include": st.column_config.CheckboxColumn(required=True)
        },
        key="mapping_editor"
    )

    # Turn DataFrame back into dict, filtered by Include
    active_map = {row.Entity: row.Alias for row in edited_df.itertuples() if row.Include}

    st.session_state["active_map"] = active_map  # Save for later decode

    if st.button("🔒 Encode", type="primary"):
        encoded_text = _encode(raw_text, active_map)
        st.text_area("Encoded text (copy & send to LLM)", value=encoded_text, height=200)
        st.code("Mapping used:\n" + json.dumps(active_map, indent=2), language="json")

# -- 3. Decode helper ----------------------------------------------------------
st.divider()

st.markdown("### Decode LLM answer")
encoded_reply = st.text_area("Paste the LLM's *encoded* reply here", height=200, key="encoded_reply")

if st.button("🔓 Decode"):
    active_map = st.session_state.get("active_map")
    if not active_map:
        st.warning("No active mapping found. Please encode some text first in this session.")
    else:
        decoded_text = _decode(encoded_reply, active_map)
        st.text_area("Decoded reply", value=decoded_text, height=200)
