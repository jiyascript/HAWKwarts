from ddgs import DDGS
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langchain.agents import create_agent
import json
import requests
from bs4 import BeautifulSoup

llm = ChatOllama(
    model="qwen3-vl:4b",
    temperature=0.0,
    reasoning=False
)

with open("iit_directory.json") as f:
    DIRECTORY = json.load(f)

@tool
def search_iit_faculty_directory(professor_name: str) -> str:
    """Search the official IIT faculty directory by name and return their
    title, department, and profile info. Use this for any question about
    an IIT professor's official role or contact info.
    """
    name_lower = professor_name.lower()
    matches = [p for p in DIRECTORY if name_lower in p["name"].lower()]

    if not matches:
        return f"No IIT directory entry found for '{professor_name}'."

    person = matches[0]
    # Fetch the individual profile page for fuller detail (bio, office, etc.)
    try:
        resp = requests.get(person["profile_url"], headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        main = soup.select_one("main") or soup.body
        detail_text = main.get_text(separator=" ", strip=True)[:1500]
    except Exception:
        detail_text = ""

    summary = (
        f"Name: {person['name']}\n"
        f"Titles: {', '.join(person['tags'])}\n"
        f"Email: {person.get('email', 'N/A')}\n"
        f"Profile: {person['profile_url']}"
    )
    if detail_text:
        summary += f"\n\nFull profile text: {detail_text}"
    return summary

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
    tools=[web_search, search_iit_faculty_directory], 
    system_prompt=(
        "You are an academic advisor at Illinois Institute of Technology. When a student asks "
        "a question about a professor "
        "call the search_iit_faculty_directory tool. When constructing the search query, use only the key terms "
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
