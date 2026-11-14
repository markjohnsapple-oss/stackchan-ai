#!/usr/bin/env python3
"""AHL ASL v7: extend verified v6 with optional natural learning and recall tools.
Only applied in an ephemeral CI checkout; preserves factory StackChan functions.
"""
from pathlib import Path

HAL = Path(__file__).resolve().parents[1] / "upstream/firmware/main/hal/hal.cpp"

def apply():
    text=HAL.read_text(encoding="utf-8")
    before="    hal_bridge::start_xiaozhi_app();"
    if text.count(before)!=1 or 'ahl.memory.search' not in text or 'asl_live::requested()' not in text:
        raise RuntimeError("STOP: verified ASL v6 memory MCP bridge missing")
    tools='''    // Read-only memory tools. Access only in ASL Companion Mode.
    McpServer::GetInstance().AddTool(
        "ahl.memory.list",
        "Only when asked to recall all saved memories, list up to eight personal facts.",
        PropertyList(),
        [](const PropertyList&) -> ReturnValue {
            if (!asl_live::requested()) return std::string("ASL Companion mode inactive");
            return ahl::getAslMemory().list();
        });
    McpServer::GetInstance().AddTool(
        "ahl.memory.status",
        "Report how many personal facts are stored and if natural learning is enabled.",
        PropertyList(),
        [](const PropertyList&) -> ReturnValue {
            if (!asl_live::requested()) return std::string("ASL Companion mode inactive");
            return ahl::getAslMemory().status();
        });
    McpServer::GetInstance().AddTool(
        "ahl.companion.capabilities",
        "When asked about myself, state my actual ASL features truthfully.",
        PropertyList(),
        [](const PropertyList&) -> ReturnValue {
            if (!asl_live::requested()) return std::string("ASL Companion mode inactive");
            return std::string(
                "I am StackChan ASL Companion v7. My cloud XiaoZhi AI can chat. "
                "I have animated expressions and a camera that can take photos; "
                "cloud image understanding depends on a vision-enabled server. "
                "I store up to 32 locally saved personal facts. Say start learning "
                "about me to enable opt-in natural learning of brief personal facts; "
                "say stop learning about me to disable it. "
                "I do not identify people by face or run a 500MB offline AI brain. "
                "My greeting uses the approved animated voice, but my live AI "
                "answers still use the configured cloud speech synthesiser.");
        });
'''
    text=text.replace(before,tools+before,1)
    HAL.write_text(text,encoding="utf-8")
    print("ASL v7 opt-in personal learning, recall and truthful capability tools applied.")

if __name__=="__main__":
    apply()
