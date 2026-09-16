from typing import Dict, Any

def generate_pitch(company: str = "[Company Name]", role: str = "[Job Title]", category: str = "uiux", recipient: str = "Hiring Team") -> Dict[str, str]:
    company = company.strip() if company else "[Company Name]"
    role = role.strip() if role else "[Job Title]"
    recipient = recipient.strip() if recipient else "Hiring Team"
    cat_lower = category.lower()

    if "graphic" in cat_lower or "visual" in cat_lower or "brand" in cat_lower:
        subject = f"Graphic Designer Application – Balogun Olamide (Portfolio Inside)"
        body = f"""Hi {recipient},

I came across your opening for {role} at {company} and wanted to reach out. I am a graphic designer and motion editor who works across the full visual pipeline—from standalone campaign assets to scalable visual brand systems.

At CareerPaddy, an ed-tech platform, I built a modular visual system that scaled across 1,397 courses and tightened our production workflow to cut marketing asset turnaround time by 30%. For corporate clients like Tratun Energy Limited and Grosvenor Global Services, I turn dense technical topics into clean, minimalist visuals that build authority on professional channels.

What I bring to your remote team:
• Tooling & Production: Adobe Photoshop, Illustrator, After Effects, Canva, Figma
• Focus: Social/campaign creatives, marketing collateral, brand guidelines, motion promo assets
• Discipline: Multi-client deadline management, async-first communication, and fast revision cycles

Portfolio & Case Studies: https://drive.google.com/drive/folders/1y1u9gG3oV... (or your portfolio link)
LinkedIn: https://linkedin.com/in/olamide-balogun-94989a417

I work comfortably across time zones, communicate proactively in async workflows, and would love to discuss how I can support {company}'s design pipeline this week.

Best regards,
Balogun Olamide
(+234) 903 708 6975
Olamidebalogun3131@gmail.com
"""
    else:  # Default to UI/UX / Product Design
        subject = f"Product / UI/UX Designer Application – Balogun Olamide"
        body = f"""Hi {recipient},

I am applying for the {role} role at {company}. I design intuitive, user-centered digital products, responsive interfaces, and structured design systems in Figma.

Through my Product Design training at TechCrush and live product builds, I focus on turning complex user workflows into clean, accessible digital experiences:

• ektós Financial (Fintech App & Design System — TechCrush):
  Designed an end-to-end mobile personal finance app and full tokenized design system (Figma auto-layout, atomic components, light/dark mode elevation, and onboarding flows) backed by competitive research across 16 global fintech products.

• Hindsight (AI Exam Intelligence Platform):
  Designed the mobile product UX, topic-frequency diagnostics, and timed mock exam interfaces for a national university innovation competition (COUCH 2026).

Figma & Tooling: Figma (Auto-layout, Components, Interactive Prototyping, Design Tokens, Wireframing, User Flows), Adobe Creative Suite, Responsive Web/Mobile UI.

Portfolio & Case Studies: https://drive.google.com/drive/folders/1y1u9gG3oV... (or your portfolio link)
LinkedIn: https://linkedin.com/in/olamide-balogun-94989a417

I work comfortably across time zones, communicate proactively in async environments, and am ready to hit the ground running for {company}.

Best regards,
Balogun Olamide
(+234) 903 708 6975
Olamidebalogun3131@gmail.com
"""

    return {
        "subject": subject,
        "body": body,
        "company": company,
        "role": role,
        "category": category
    }
