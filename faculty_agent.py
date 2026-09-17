from ddgs import DDGS
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langchain.agents import create_agent

llm = ChatOllama(
    model="qwen3-vl:4b",
    temperature=0.0,
    reasoning=False
)

@tool
def web_search(query: str) -> str:
    """Search the web for current events, live facts, and recent news updates."""

    scoped_query = f"{query} Illinois Institute of Technology Chicago"
    try:
        # Fetch the top 3 results from DuckDuckGo safely
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(scoped_query, max_results=3)]
            
        if not results:
            return "No relevant search results found."
        
        # Format the results into a clean string for the LLM to read
        formatted_results = []
        for r in results:
            formatted_results.append(f"Title: {r['title']}\nURL: {r['href']}\nSnippet: {r['body']}\n---")
        return "\n".join(formatted_results)
        
    except Exception as e:
        return f"An error occurred while searching the web: {str(e)}"

agent = create_agent(
    model=llm, 
    tools=[web_search], 
    system_prompt=(
        "You are an academic advisor at Illinois Institute of Technology. When a student asks "
        "a question "
        "call the web_search tool. When constructing the search query, use only the key terms "
        "from the user's question — do NOT add a year, date range, or your own assumptions "
        "about what 'recent' means. Your training data may be outdated; let the search results, "
        "not your prior beliefs, determine the timeframe. Base your final answer strictly on "
        "what the search results say and summarize it. "
        "If the question does not concern academic advising or is irrelevant, remind "
        "the user you are an academic advisor and refuse to answer the question. "
        "Always include a source or sources for your answer with a link if possible. "
    )
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "ENTER QUESTION HERE"}]}
)

print(result["messages"][-1].content)
