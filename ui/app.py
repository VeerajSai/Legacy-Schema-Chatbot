"""Streamlit chat UI. Run with: streamlit run ui/app.py"""
from __future__ import annotations

import streamlit as st

from pipeline.orchestrator import answer_question

ROLES = ["admin", "sales_analyst", "finance_analyst", "hr_admin", "exec"]

st.set_page_config(page_title="NL2SQL Chatbot", page_icon="\U0001F4CA")
st.title("NL2SQL Chatbot")
st.caption("Ask a question about the legacy database in plain English.")

role = st.selectbox("Role", ROLES, index=ROLES.index("sales_analyst"))
question = st.text_input("Your question")
ask = st.button("Ask")

if "history" not in st.session_state:
    st.session_state.history = []  # [{"question", "sql", "tables"}]

if ask and question.strip():
    with st.spinner("Thinking..."):
        try:
            ctx = answer_question(
                question, user_id="streamlit-user", role=role,
                conversation=st.session_state.history,
            )
        except Exception as e:  # noqa: BLE001 -- surface pipeline errors in the UI, don't crash the app
            st.error(f"Pipeline error: {type(e).__name__}: {e}")
            ctx = None

    if ctx is not None:
        if ctx.clarification_question:
            st.warning(f"Clarification needed: {ctx.clarification_question}")
        elif ctx.blocked_reason:
            st.error(ctx.blocked_reason)
        else:
            st.markdown(f"**Answer:** {ctx.answer or '_(no answer produced)_'}")
            if ctx.cache_hit:
                st.caption(f"⚡ served from cache ({ctx.cache_hit})")

            execution = ctx.execution
            with st.expander("Generated SQL & result details"):
                st.code(ctx.sql_candidate or "-- no SQL generated --", language="sql")
                if execution:
                    st.write(f"Rows returned: {execution.row_count}")
                    if execution.truncated:
                        st.info("Result was truncated by the row cap.")
                    if execution.error:
                        st.error(f"Execution error: {execution.error}")

        st.session_state.history.append({
            "question": question,
            "sql": ctx.sql_candidate,
            "tables": list(ctx.graph.all_tables) if ctx.graph else [],
        })

if st.session_state.history:
    with st.expander("Conversation history"):
        for turn in st.session_state.history:
            st.write(turn)
