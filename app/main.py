import streamlit as st
from app.agents import orchestrator
from app.agents.orchestrator import Orchestrator

st.set_page_config(page_title="Market Research Brief", page_icon="📊", layout="wide")

st.title("📊 Multi-Agent Market Research Brief")
st.markdown(
    "Enter a company or industry topic to generate a research brief using a 4-agent workflow."
)


# Initialize Orchestrator once and cache
@st.cache_resource
def get_orchestrator():
    return Orchestrator()


try:
    orchestrator = get_orchestrator()
except Exception as e:
    st.error(f"Failed to initialize LLM Orchestrator: {e}")
    st.info(
        "Check your `.env` file to ensure `OPENAI_API_KEY` (or Ollama) is configured correctly."
    )
    st.stop()


# Query Input
query = st.text_input(
    label="Company or Industry Topic",
    placeholder="e.g., Analyze the food delivery market in Nepal",
)
start_button = st.button("Start Research", type="primary", disabled=not query.strip())


if start_button:
    with st.status("Executing Multi-Agent Workflow...", expanded=True) as status:
        st.write("**Orchestrator**: Initializing state...")
        state = orchestrator.start_workflow(query)

        st.write("**Researcher**: Gathering web search evidence...")
        state = orchestrator.researcher.run(state)
        st.write(f"✓ Researcher collected {len(state.findings)} evidence points.")

        st.write("**Analyst**: Synthesizing initial brief draft...")
        state = orchestrator.analyst.run(state)
        st.write("✓ Initial draft completed.")

        st.write("**Critic**: Reviewing draft against evidence...")
        state = orchestrator.critic.run(state)

        if state.criticism:
            if state.criticism.revision_required and state.revision_count < 1:
                st.warning(
                    "Critic requested revision. Feedback: "
                    + "; ".join(state.criticism.feedback)
                )
                st.write("**Analyst**: Again Generating revised brief...")
                state.revision_count += 1
                state = orchestrator.analyst.run(state)
                st.write("✓ Revised brief generated.")
            else:
                st.write("✓ Critic approved draft.")

        state.final_brief = state.analysis
        status.update(
            label="Research Brief Complete!", state="complete", expanded=False
        )

    # Display Final Brief
    if state.final_brief:
        st.subheader("📋 Research Brief")

        # 1. Summary
        st.markdown("### 1. Executive Summary")
        st.write(state.final_brief.summary)

        # 2. Competitors
        st.markdown("### 2. Main Competitors (Up to 2)")
        if state.final_brief.competitors:
            cols = st.columns(len(state.final_brief.competitors))
            for idx, comp in enumerate(state.final_brief.competitors):
                cols[idx].info(f"🏢 **{comp}**")
        else:
            st.write("No direct competitors identified from available findings.")

        # 3. Key Observations
        st.markdown("### 3. Key Observations")
        for obs in state.final_brief.key_observations:
            st.markdown(f"- {obs}")

        # 4. Sources & Missing Information
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 4. Sources Cited")
            sources = state.final_brief.sources or [f.source for f in state.findings if f.source]
            unique_sources = list(dict.fromkeys(sources))

            if unique_sources:
                for src in unique_sources:
                    if src.startswith("http"):
                        st.markdown(f"- [{src}]({src})")
                    else:
                        st.markdown(f"- {src}")
            else:
                st.write("No external sources recorded.")

        with col2:
            st.markdown("### 5. Missing / Uncertain Information")
            if state.final_brief.missing_info:
                for item in state.final_brief.missing_info:
                    st.markdown(f"- {item}")
            else:
                st.write("No critical information gaps identified.")

        # Display the overall Confidence from your Analysis model
        if hasattr(state.final_brief, "confidence") and state.final_brief.confidence:
            st.caption(
                f"**Analyst Confidence Level:** {state.final_brief.confidence.capitalize()}"
            )

        # Show agent thought process and raw findings in an expander
        with st.expander("🔍 View Raw Research Findings & Critic Review"):
            st.write("**Critic Feedback:**")
            st.json(state.criticism.model_dump() if state.criticism else {})
            st.write("**Raw Search Findings:**")
            st.json([f.model_dump() for f in state.findings])
