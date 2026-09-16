import re
import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Any
from database import save_job

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html, application/xhtml+xml, application/xml;q=0.9,*/*;q=0.8"
}

def clean_html(html_text: str) -> str:
    if not html_text:
        return ""
    soup = BeautifulSoup(html_text, "html.parser")
    return soup.get_text(separator=" ", strip=True)

def is_design_role(title: str, description: str = "", tags: Any = None) -> bool:
    """Strictly filter for genuine design positions only"""
    title_lower = title.lower()
    
    # Non-design disqualifiers
    disqualifiers = [
        "sales manager", "sales advisor", "handyperson", "cabin crew", "flight attendant",
        "service desk", "customer service", "receptionist", "bookkeeper", "driver",
        "accountant", "legal", "nurse", "cook", "chef", "warehouse", "cashier",
        "plumber", "electrician", "mechanic", "security guard", "cleaner", "copywriter", 
        "freelance writer", "inside sales", "business development", "data labeling",
        "speculative application", "small batches", "content reviewer", "software engineer",
        "backend", "full stack", "devops", "cloud architect", "data engineer", "sourcing partner"
    ]
    if any(dq in title_lower for dq in disqualifiers):
        return False
        
    # Required design title keywords
    strict_design_title_keywords = [
        "design", "ui", "ux", "product designer", "graphic", "visual", "brand", 
        "figma", "illustrator", "creative", "motion", "art director", "prototyp",
        "animat", "3d artist", "design system", "interaction", "web designer", "thumbnail"
    ]
    if any(kw in title_lower for kw in strict_design_title_keywords):
        return True
        
    return False

def classify_job(title: str, description: str, tags: Any = None) -> Dict[str, Any]:
    tag_str = ""
    if isinstance(tags, list):
        for t in tags:
            if isinstance(t, dict):
                tag_str += " " + t.get("term", "")
            elif isinstance(t, str):
                tag_str += " " + t
                
    text = f"{title} {description} {tag_str}".lower()
    
    is_uiux = any(kw in text for kw in [
        "ui/ux", "ui / ux", "ux/ui", "ui designer", "ux designer", 
        "product design", "product designer", "user experience", 
        "user interface", "interaction design", "figma", "wireframe", 
        "prototype", "design system", "mobile designer", "web designer"
    ])
    is_graphic = any(kw in text for kw in [
        "graphic", "visual design", "visual designer", "brand design", 
        "brand designer", "motion", "illustrator", "photoshop", 
        "creative designer", "marketing design", "marketing designer", 
        "social media design", "canva", "video editor", "banner", "art director", "thumbnail"
    ])
    
    if is_uiux and is_graphic:
        category = "UI/UX & Graphic Design"
    elif is_uiux:
        category = "UI/UX & Product Design"
    elif is_graphic:
        category = "Graphic & Visual Design"
    else:
        category = "UI/UX & Product Design" if ("ui" in title.lower() or "ux" in title.lower() or "product" in title.lower()) else "Graphic & Visual Design"

    title_lower = title.lower()
    if any(kw in title_lower for kw in ["senior", "lead", "principal", "director", "head of", "staff", "vp", "sr.", "sr "]):
        level = "Senior / Lead"
    elif any(kw in title_lower for kw in ["junior", "entry", "intern", "associate", "beginner", "graduate", "assistant"]):
        level = "Junior / Entry"
    else:
        level = "Intermediate / Mid"

    return {
        "category": category,
        "level": level
    }

def is_worldwide_location(location_str: str) -> bool:
    if not location_str:
        return True
    loc = location_str.lower().strip()
    
    if any(p in loc for p in ["anywhere", "worldwide", "global", "remote - anywhere", "all", "work from anywhere", "latam/apac/emea"]):
        return True
        
    restricted_keywords = [
        "us only", "usa only", "united states only", "only in the us", 
        "eu only", "europe only", "uk only", "canada only", 
        "germany only", "us/canada only", "north america only", "est only", "pst only"
    ]
    for r in restricted_keywords:
        if r in loc:
            return False
            
    return True

# -------------------------------------------------------------
# 100% FREE-TO-APPLY JOB BOARD INTEGRATIONS
# -------------------------------------------------------------

def fetch_reddit_design_jobs() -> int:
    """Fetch [Hiring] posts from Reddit r/designjobs, r/forhire, r/remotejobs"""
    subreddits = ["designjobs", "forhire", "remotejobs"]
    count = 0
    
    for sub in subreddits:
        try:
            url = f"https://www.reddit.com/r/{sub}/new.rss"
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                feed = feedparser.parse(r.text)
                for entry in feed.entries:
                    raw_title = entry.get("title", "").strip()
                    raw_title_lower = raw_title.lower()
                    
                    # We only want [Hiring] posts, ignore [For Hire]
                    if not any(h in raw_title_lower for h in ["[hiring]", "(hiring)", "hiring:"]):
                        continue
                        
                    # Clean title
                    clean_title = re.sub(r'\[hiring\]|\(hiring\)', '', raw_title, flags=re.IGNORECASE).strip()
                    if not clean_title:
                        continue
                        
                    desc = clean_html(entry.get("summary", ""))
                    if not is_design_role(clean_title, desc):
                        continue
                        
                    # Extract salary / rate if present in title or desc
                    salary_match = re.search(r'(\$\d+[\d,]*\s*(?:-\s*\$?\d+[\d,]*)?\s*(?:\/\s*hr|\/hr|hr|hourly|per hour|k|k\/yr)?)', f"{clean_title} {desc}", re.IGNORECASE)
                    salary = salary_match.group(1) if salary_match else "Budget in Post"
                    
                    author = entry.get("author", "").replace("/u/", "").strip()
                    company = f"Reddit client (@{author})" if author else f"Reddit (r/{sub})"
                    url_link = entry.get("link", "")
                    pub_date = entry.get("published", "")
                    try:
                        date_str = datetime.strptime(pub_date[:16], "%a, %d %b %Y").strftime("%Y-%m-%d")
                    except:
                        date_str = datetime.utcnow().strftime("%Y-%m-%d")
                        
                    classification = classify_job(clean_title, desc)
                    
                    saved = save_job({
                        "source": f"Reddit (r/{sub})",
                        "external_id": f"reddit_{entry.get('id', url_link)}",
                        "title": clean_title,
                        "company": company,
                        "location": "Remote (Worldwide / DM Client)",
                        "url": url_link,
                        "description": desc[:1200],
                        "category": classification["category"],
                        "level": classification["level"],
                        "salary": salary,
                        "is_worldwide": True,
                        "date_posted": date_str
                    })
                    if saved:
                        count += 1
        except Exception as e:
            print(f"Error fetching Reddit r/{sub}: {e}")
            
    return count

def fetch_remotive_jobs() -> int:
    """Remotive: 100% Free direct ATS apply links"""
    count = 0
    try:
        url = "https://remotive.com/api/remote-jobs?category=design"
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code == 200:
            data = r.json()
            for j in data.get("jobs", []):
                title = j.get("title", "")
                company = j.get("company_name", "")
                loc = j.get("candidate_required_location", "Anywhere")
                desc = clean_html(j.get("description", ""))
                url_link = j.get("url", "")
                salary = j.get("salary", "") or "Disclosed on Apply"
                date_str = j.get("publication_date", "")[:10]
                tags = j.get("tags", [])
                
                if not is_design_role(title, desc, tags):
                    continue
                
                classification = classify_job(title, desc, tags)
                worldwide = is_worldwide_location(loc)
                
                saved = save_job({
                    "source": "Remotive (Free Direct Apply)",
                    "external_id": f"remotive_{j.get('id')}",
                    "title": title,
                    "company": company,
                    "location": f"Remote ({loc})" if loc else "Remote (Worldwide)",
                    "url": url_link,
                    "description": desc[:1200],
                    "category": classification["category"],
                    "level": classification["level"],
                    "salary": salary,
                    "is_worldwide": worldwide,
                    "date_posted": date_str
                })
                if saved:
                    count += 1
    except Exception as e:
        print(f"Error fetching Remotive: {e}")
    return count

def fetch_weworkremotely_jobs() -> int:
    """WeWorkRemotely: 100% Free direct company apply"""
    count = 0
    try:
        feed = feedparser.parse("https://weworkremotely.com/categories/remote-design-jobs.rss")
        for entry in feed.entries:
            raw_title = entry.get("title", "")
            if ":" in raw_title:
                parts = raw_title.split(":", 1)
                company = parts[0].strip()
                title = parts[1].strip()
            else:
                company = "Remote Team"
                title = raw_title
                
            loc = entry.get("region", "") or entry.get("country", "") or "Anywhere in the World"
            desc = clean_html(entry.get("summary", ""))
            url_link = entry.get("link", "")
            pub_date = entry.get("published", "")
            tags = entry.get("tags", [])
            
            if not is_design_role(title, desc, tags):
                continue
                
            try:
                date_str = datetime.strptime(pub_date[:16], "%a, %d %b %Y").strftime("%Y-%m-%d")
            except:
                date_str = datetime.utcnow().strftime("%Y-%m-%d")
                
            classification = classify_job(title, desc, tags)
            worldwide = is_worldwide_location(loc)
            
            saved = save_job({
                "source": "WeWorkRemotely (Free Direct Apply)",
                "external_id": f"wwr_{entry.get('id', url_link)}",
                "title": title,
                "company": company,
                "location": f"Remote ({loc})" if loc else "Remote (Worldwide)",
                "url": url_link,
                "description": desc[:1200],
                "category": classification["category"],
                "level": classification["level"],
                "salary": "Disclosed on Apply",
                "is_worldwide": worldwide,
                "date_posted": date_str
            })
            if saved:
                count += 1
    except Exception as e:
        print(f"Error fetching WWR: {e}")
    return count

def fetch_himalayas_jobs() -> int:
    """Himalayas: 100% Free direct Greenhouse / Lever / Ashby link"""
    count = 0
    try:
        url = "https://himalayas.app/jobs/api?search=design"
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code == 200:
            data = r.json()
            for j in data.get("jobs", []):
                title = j.get("title", "")
                company = j.get("companyName", "")
                loc = ", ".join(j.get("locationRestrictions", [])) or "Worldwide"
                desc = clean_html(j.get("description", ""))
                url_link = j.get("applicationUrl") or f"https://himalayas.app/jobs/{j.get('slug', '')}"
                
                if not is_design_role(title, desc, j.get("categories", [])):
                    continue
                    
                min_sal = j.get("minSalary")
                max_sal = j.get("maxSalary")
                currency = j.get("salaryCurrency", "USD")
                if min_sal and max_sal:
                    salary = f"${min_sal:,} - ${max_sal:,} {currency}"
                elif min_sal:
                    salary = f"${min_sal:,}+ {currency}"
                else:
                    salary = "Disclosed on Apply"
                    
                pub_ts = j.get("pubDate")
                date_str = datetime.fromtimestamp(pub_ts).strftime("%Y-%m-%d") if pub_ts else datetime.utcnow().strftime("%Y-%m-%d")
                
                classification = classify_job(title, desc, j.get("categories", []))
                worldwide = is_worldwide_location(loc)
                
                saved = save_job({
                    "source": "Himalayas (Free Direct ATS)",
                    "external_id": f"himalayas_{j.get('id', url_link)}",
                    "title": title,
                    "company": company,
                    "location": f"Remote ({loc})" if loc else "Remote (Worldwide)",
                    "url": url_link,
                    "description": desc[:1200],
                    "category": classification["category"],
                    "level": classification["level"],
                    "salary": salary,
                    "is_worldwide": worldwide,
                    "date_posted": date_str
                })
                if saved:
                    count += 1
    except Exception as e:
        print(f"Error fetching Himalayas: {e}")
    return count

def run_all_scrapers() -> Dict[str, int]:
    """Run all 100% free-to-apply sources (Reddit, WWR, Remotive, Himalayas)"""
    reddit_count = fetch_reddit_design_jobs()
    remotive_count = fetch_remotive_jobs()
    wwr_count = fetch_weworkremotely_jobs()
    himalayas_count = fetch_himalayas_jobs()
    total_new = reddit_count + remotive_count + wwr_count + himalayas_count
    return {
        "reddit": reddit_count,
        "remotive": remotive_count,
        "weworkremotely": wwr_count,
        "himalayas": himalayas_count,
        "total_new": total_new
    }
