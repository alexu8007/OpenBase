import json
from typing import Dict, Any, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain.schema.output_parser import StrOutputParser

from app.config.llm_config import get_agent_configured_llm
from app.utils.logger import logger

class ArchitectAgent:
    """
    An agent that provides high-level architectural and innovation recommendations
    based on a comprehensive analysis of the codebase.
    """
    
    def __init__(self, provider: Optional[str] = None):
        # Use a slightly higher temperature for creative, strategic recommendations
        # Use agent-specific provider if no provider specified
        if provider is None:
            self.llm = get_agent_configured_llm('architect', temperature=0.6)
        else:
            # Maintain backward compatibility for explicit provider
            from app.config.llm_config import get_configured_llm
            self.llm = get_configured_llm(provider=provider, temperature=0.6)
        self.prompt_template = self._create_prompt_template()

    def _create_prompt_template(self) -> ChatPromptTemplate:
        """Creates the prompt template for the architect agent."""
        
        system_prompt = """You are an expert software architect and product manager. Analyze the provided codebase context and generate a concise list of high-impact recommendations.

For each recommendation, provide a single line in the following format:
`**Category:** Recommendation Title - **Technology:** Tech Involved - **Implementation:** Brief Plan - **Benefit:** Key Advantage`

Use the following categories:
- `New Feature`
- `Codebase Improvement`
- `Tech Upgrade`
- `UX Enhancement`
- `Testing`
- `Scalability`
- `Security`

Focus only on the most critical and innovative ideas. Avoid lengthy explanations. The output should be a simple, scannable list of actions."""
        
        human_prompt = """
**Project Context:**

**FULL CODEBASE CONTENT:**
```
{full_codebase_content}
```

**FILE INVENTORY:**
{file_inventory}

**DEPENDENCY GRAPH:**
{dependency_graph}

**ARCHITECTURE ANALYSIS:**
{architecture_analysis}
"""
        return ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", human_prompt)
        ])

    async def run(self, analysis_report: Dict[str, Any]) -> str:
        """
        Generates architectural and innovation recommendations.

        Args:
            analysis_report: The comprehensive report from the AdvancedContextEngine.

        Returns:
            A string containing the formatted recommendations.
        """
        logger.info("🏛️ Running Architect Agent for concise recommendations...")
        
        chain = self.prompt_template | self.llm | StrOutputParser()

        def to_json(data):
            return json.dumps(data, indent=2, default=str)

        try:
            # Note: The user removed 'contextual_insights', so it's omitted here.
            response = await chain.ainvoke({
                "file_inventory": to_json(analysis_report.get("file_inventory", {})),
                "dependency_graph": to_json(analysis_report.get("dependency_graph", {})),
                "architecture_analysis": to_json(analysis_report.get("architecture_analysis", {})),
                "full_codebase_content": to_json(analysis_report.get("full_codebase_content", {}))
            })
            logger.info("✅ Architect Agent completed successfully.")
            return response
        except Exception as e:
            logger.error(f"Architect Agent failed to generate recommendations: {e}", exc_info=True)
            return f"### Error: Could not generate architectural recommendations.\nAn unexpected error occurred: {e}" 