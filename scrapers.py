import re
import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
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

def fetch_telegram_channel_jobs() -> int:
    """Fetch recent design & intern posts from public Telegram channels (t.me/s/)"""
    count = 0
    try:
        from database import get_settings
        settings = get_settings()
        custom_channels_str = settings.get("monitored_telegram_channels", "")
        if custom_channels_str.strip():
            channels = [c.strip().lstrip("@") for c in custom_channels_str.split(",") if c.strip()]
        else:
            channels = ["remoteinternships", "entrylevelremote", "techjobs_africa", "designjobsng"]
            
        for ch in channels:
            url = f"https://t.me/s/{ch}"
            try:
                r = requests.get(url, headers=HEADERS, timeout=10)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    messages = soup.select(".tgme_widget_message")
                    for msg in messages:
                        text_el = msg.select_one(".tgme_widget_message_text")
                        if not text_el:
                            continue
                        full_text = clean_html(str(text_el))
                        text_lower = full_text.lower()
                        
                        # Filter for design / creative roles
                        has_design = any(kw in text_lower for kw in [
                            "graphic", "ui/ux", "ui / ux", "ux/ui", "product design", "figma", 
                            "photoshop", "illustrator", "visual design", "brand design",
                            "creative intern", "design intern", "junior designer", "thumbnail",
                            "canva", "creative assistant"
                        ])
                        if not has_design:
                            continue
                            
                        link_tag = text_el.find("a", href=True)
                        post_id_link = msg.select_one(".tgme_widget_message_date")
                        external_id = msg.get("data-post", f"{ch}_{hash(full_text[:50])}")
                        
                        if link_tag and link_tag["href"].startswith("http"):
                            url_link = link_tag["href"]
                        elif post_id_link and post_id_link.get("href"):
                            url_link = post_id_link["href"]
                        else:
                            url_link = f"https://t.me/{ch}"
                            
                        lines = [line.strip() for line in full_text.splitlines() if line.strip()]
                        title = lines[0][:90] if lines else "Design Internship / Role"
                        
                        salary_match = re.search(r'(\$\d+[\d,]*\s*(?:-\s*\$?\d+[\d,]*)?|\b\d+k\b|₦[\d,]+|\bpaid\b|\bstipend\b|\bcompetitive\b)', full_text, re.IGNORECASE)
                        salary = salary_match.group(1) if salary_match else "See Telegram Post"
                        
                        classification = classify_job(title, full_text)
                        if any(kw in text_lower for kw in ["intern", "internship", "junior", "entry", "beginner", "apprentice"]):
                            classification["level"] = "Junior / Entry"
                            
                        saved = save_job({
                            "source": f"Telegram (@{ch})",
                            "external_id": f"tg_{external_id}",
                            "title": title,
                            "company": f"Telegram (@{ch})",
                            "location": "Remote (Worldwide / Telegram)",
                            "url": url_link,
                            "description": full_text[:1200],
                            "category": classification["category"],
                            "level": classification["level"],
                            "salary": salary,
                            "is_worldwide": True,
                            "date_posted": datetime.utcnow().strftime("%Y-%m-%d")
                        })
                        if saved:
                            count += 1
            except Exception as e:
                print(f"Error fetching Telegram channel @{ch}: {e}")
    except Exception as e:
        print(f"Error in fetch_telegram_channel_jobs: {e}")
    return count

def fetch_twitter_design_jobs() -> int:
    """Fetch recent hiring tweets from open Nitter mirrors / RSS feeds"""
    count = 0
    nitter_instances = [
        "https://nitter.privacydev.net",
        "https://nitter.poast.org",
        "https://nitter.lucabased.xyz"
    ]
    query = "hiring (graphic designer OR ui/ux OR design intern) remote"
    
    for instance in nitter_instances:
        try:
            url = f"{instance}/search/rss?f=tweets&q={requests.utils.quote(query)}"
            r = requests.get(url, headers=HEADERS, timeout=8)
            if r.status_code == 200:
                feed = feedparser.parse(r.text)
                if feed.entries:
                    for entry in feed.entries[:10]:
                        title = clean_html(entry.get("title", ""))
                        link = entry.get("link", "").replace(instance, "https://x.com")
                        desc = clean_html(entry.get("summary", ""))
                        author = entry.get("author", "X User")
                        
                        if not is_design_role(title, desc):
                            continue
                            
                        classification = classify_job(title, desc)
                        if any(kw in f"{title} {desc}".lower() for kw in ["intern", "internship", "junior", "beginner"]):
                            classification["level"] = "Junior / Entry"
                            
                        saved = save_job({
                            "source": "X / Twitter",
                            "external_id": f"x_{entry.get('id', link)}",
                            "title": title[:90],
                            "company": f"X (@{author.lstrip('@')})",
                            "location": "Remote (DM Client on X)",
                            "url": link,
                            "description": desc[:1200],
                            "category": classification["category"],
                            "level": classification["level"],
                            "salary": "DM on X for Details",
                            "is_worldwide": True,
                            "date_posted": datetime.utcnow().strftime("%Y-%m-%d")
                        })
                        if saved:
                            count += 1
                    break
        except Exception as e:
            continue
            
    return count

def parse_jobberman_date(date_str: str) -> str:
    now = datetime.utcnow()
    date_str_l = date_str.lower().strip()
    if "hour" in date_str_l or "minute" in date_str_l or "today" in date_str_l or "just now" in date_str_l:
        return now.strftime("%Y-%m-%d")
    elif "yesterday" in date_str_l:
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")
    match = re.search(r'(\d+)\s+(day|week|month)', date_str_l)
    if match:
        num = int(match.group(1))
        unit = match.group(2)
        if unit == "day":
            return (now - timedelta(days=num)).strftime("%Y-%m-%d")
        elif unit == "week":
            return (now - timedelta(weeks=num)).strftime("%Y-%m-%d")
        elif unit == "month":
            return (now - timedelta(days=num*30)).strftime("%Y-%m-%d")
    return now.strftime("%Y-%m-%d")

def fetch_jobberman_jobs() -> int:
    """Jobberman Nigeria: Direct job applications for creative, UI/UX & graphic design roles"""
    count = 0
    queries = ["design", "graphic+designer", "ui%2Fux", "product+designer", "creative+designer"]
    seen_urls = set()
    
    for q in queries:
        try:
            url = f"https://www.jobberman.com/jobs?q={q}"
            r = requests.get(url, headers=HEADERS, timeout=12)
            if r.status_code != 200:
                continue
                
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.select("[data-cy='listing-cards-components']")
            
            for card in cards:
                title_a = card.select_one("a[data-cy='listing-title-link']") or card.find("a", href=lambda h: h and "/listings/" in h)
                if not title_a:
                    continue
                    
                title = title_a.get_text(strip=True)
                job_url = title_a.get("href", "")
                if not job_url:
                    continue
                if not job_url.startswith("http"):
                    job_url = f"https://www.jobberman.com{job_url}"
                    
                if job_url in seen_urls:
                    continue
                seen_urls.add(job_url)
                
                slug = job_url.rstrip("/").split("/")[-1]
                external_id = f"jobberman_{slug}"
                
                # Description
                desc_el = card.find("p", class_=lambda c: c and ("md:text-gray-500" in c or "md:pl-5" in c))
                desc = desc_el.get_text(strip=True) if desc_el else ""
                if not desc:
                    paras = [p.get_text(strip=True) for p in card.find_all("p") if p.get_text(strip=True)]
                    if paras:
                        desc = max(paras, key=len)
                
                # Strict filter for design roles
                if not is_design_role(title, desc):
                    continue
                    
                # Company
                company_a = card.find("a", href=lambda h: h and "/company/" in h)
                if company_a:
                    company = company_a.get_text(strip=True)
                else:
                    comp_p = card.find("p", class_=lambda c: c and "text-blue-700" in c)
                    company = comp_p.get_text(strip=True) if comp_p else "Jobberman Employer"
                if not company or company == title:
                    company = "Jobberman Employer"
                    
                # Badges / metadata: location, salary, job type
                badges = [s.get_text(strip=True) for s in card.select(".bg-brand-secondary-100") if s.get_text(strip=True)]
                
                location = "Nigeria"
                salary = "Disclosed on Apply"
                
                for b in badges:
                    b_lower = b.lower()
                    if any(loc_kw in b_lower for loc_kw in ["remote", "work from home", "lagos", "abuja", "nigeria", "hybrid", "port harcourt", "ibadan"]):
                        location = b
                    elif any(sal_kw in b_lower for sal_kw in ["ngn", "₦", "confidential", "k -", "k/"]):
                        salary = b if b.lower() != "confidential" else "Disclosed on Apply"
                        
                # Date posted
                date_p = card.find("p", string=lambda s: s and ("ago" in s.lower() or "today" in s.lower() or "yesterday" in s.lower()))
                if not date_p:
                    date_p = card.select_one("div.ml-auto p")
                date_str = parse_jobberman_date(date_p.get_text(strip=True)) if date_p else datetime.utcnow().strftime("%Y-%m-%d")
                
                classification = classify_job(title, desc)
                
                loc_lower = location.lower()
                is_remote = "remote" in loc_lower or "work from home" in loc_lower
                if is_remote:
                    loc_display = location if location.lower().startswith("remote") else f"Remote ({location})"
                else:
                    loc_display = f"{location} (Nigeria)"
                    
                saved = save_job({
                    "source": "Jobberman (Nigeria)",
                    "external_id": external_id,
                    "title": title,
                    "company": company,
                    "location": loc_display,
                    "url": job_url,
                    "description": desc[:1200],
                    "category": classification["category"],
                    "level": classification["level"],
                    "salary": salary,
                    "is_worldwide": is_remote or is_worldwide_location(location),
                    "date_posted": date_str
                })
                if saved:
                    count += 1
        except Exception as e:
            print(f"Error fetching Jobberman query {q}: {e}")
            
    return count

def fetch_freelancer_jobs() -> int:
    """Freelancer.com: CcHUB Technical Partner active freelance projects API"""
    count = 0
    queries = ["graphic design", "ui ux design", "logo design", "product design", "web design"]
    seen_ids = set()
    
    for q in queries:
        try:
            url = f"https://www.freelancer.com/api/projects/0.1/projects/active/?query={requests.utils.quote(q)}&job_details=true&limit=25"
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                data = r.json()
                for p in data.get("result", {}).get("projects", []):
                    pid = p.get("id")
                    if not pid or pid in seen_ids:
                        continue
                    seen_ids.add(pid)
                    
                    title = p.get("title", "").strip()
                    desc = p.get("preview_description", "").strip()
                    
                    if not is_design_role(title, desc):
                        continue
                        
                    seo_url = p.get("seo_url", "")
                    job_url = f"https://www.freelancer.com/projects/{seo_url}" if seo_url else f"https://www.freelancer.com/projects/{pid}"
                    
                    budget = p.get("budget", {})
                    currency = p.get("currency", {}).get("code", "USD")
                    min_b = budget.get("minimum")
                    max_b = budget.get("maximum")
                    if min_b and max_b:
                        salary = f"${min_b:g} - ${max_b:g} {currency}"
                    elif min_b:
                        salary = f"${min_b:g}+ {currency}"
                    else:
                        salary = "Disclosed on Bid"
                        
                    submit_date = p.get("submitdate")
                    date_str = datetime.fromtimestamp(submit_date).strftime("%Y-%m-%d") if submit_date else datetime.utcnow().strftime("%Y-%m-%d")
                    
                    classification = classify_job(title, desc)
                    
                    saved = save_job({
                        "source": "Freelancer (CcHUB Partner)",
                        "external_id": f"freelancer_{pid}",
                        "title": title,
                        "company": "Freelancer Client",
                        "location": "Remote (Worldwide / Freelancer)",
                        "url": job_url,
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
            print(f"Error fetching Freelancer query {q}: {e}")
            
    return count

def run_all_scrapers() -> Dict[str, int]:
    """Run all 100% free-to-apply sources: Telegram, Reddit, X/Twitter, WWR, Remotive, Himalayas, Jobberman, Freelancer"""
    telegram_count = fetch_telegram_channel_jobs()
    reddit_count = fetch_reddit_design_jobs()
    twitter_count = fetch_twitter_design_jobs()
    remotive_count = fetch_remotive_jobs()
    wwr_count = fetch_weworkremotely_jobs()
    himalayas_count = fetch_himalayas_jobs()
    jobberman_count = fetch_jobberman_jobs()
    freelancer_count = fetch_freelancer_jobs()
    total_new = telegram_count + reddit_count + twitter_count + remotive_count + wwr_count + himalayas_count + jobberman_count + freelancer_count
    return {
        "telegram": telegram_count,
        "reddit": reddit_count,
        "twitter": twitter_count,
        "remotive": remotive_count,
        "weworkremotely": wwr_count,
        "himalayas": himalayas_count,
        "jobberman": jobberman_count,
        "freelancer": freelancer_count,
        "total_new": total_new
    }

