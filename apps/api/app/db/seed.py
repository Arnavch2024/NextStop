import uuid
from typing import Any, Dict, List, Optional

from supabase import Client

from app.logger import logger

# --- Mumbai Colleges (~40) ---
MUMBAI_COLLEGES: List[Dict[str, Any]] = [
    # Engineering Colleges
    {"name": "IIT Bombay", "city": "Mumbai", "placement_url": "https://placements.iitb.ac.in"},
    {
        "name": "Veermata Jijabai Technological Institute (VJTI)",
        "city": "Mumbai",
        "placement_url": "https://vjti.ac.in/placements",
    },
    {
        "name": "Sardar Patel Institute of Technology (SPIT)",
        "city": "Mumbai",
        "placement_url": "https://spit.ac.in/placements",
    },
    {
        "name": "Dwarkadas J. Sanghvi College of Engineering (DJSCE)",
        "city": "Mumbai",
        "placement_url": "https://djsce.ac.in/placements",
    },
    {
        "name": "Thadomal Shahani Engineering College (TSEC)",
        "city": "Mumbai",
        "placement_url": "https://tsec.edu/placements",
    },
    {
        "name": "Fr. Conceicao Rodrigues College of Engineering (CRCE)",
        "city": "Mumbai",
        "placement_url": "https://frcrce.ac.in/placements",
    },
    {
        "name": "K. J. Somaiya College of Engineering (KJSCE)",
        "city": "Mumbai",
        "placement_url": "https://kjsce.somaiya.edu/placements",
    },
    {
        "name": "Vidyalankar Institute of Technology (VIT)",
        "city": "Mumbai",
        "placement_url": "https://vit.edu.in/placements",
    },
    {
        "name": "Vivekanand Education Society Institute of Technology (VESIT)",
        "city": "Mumbai",
        "placement_url": "https://vesit.ves.ac.in/placements",
    },
    {
        "name": "Sardar Patel College of Engineering (SPCE)",
        "city": "Mumbai",
        "placement_url": "https://spce.ac.in/placements",
    },
    {
        "name": "Don Bosco Institute of Technology (DBIT)",
        "city": "Mumbai",
        "placement_url": "https://dbit.in/placements",
    },
    {
        "name": "Mukesh Patel School of Technology Management & Engineering (MPSTME)",
        "city": "Mumbai",
        "placement_url": "https://engineering.nmims.edu/placements",
    },
    {
        "name": "Atharva College of Engineering",
        "city": "Mumbai",
        "placement_url": "https://atharvacoe.ac.in/placements",
    },
    {"name": "Pillai College of Engineering", "city": "Mumbai", "placement_url": "https://pce.ac.in/placements"},
    {
        "name": "Rajiv Gandhi Institute of Technology (RGIT)",
        "city": "Mumbai",
        "placement_url": "https://mctrgit.ac.in/placements",
    },
    {
        "name": "Xavier Institute of Engineering (XIE)",
        "city": "Mumbai",
        "placement_url": "https://xavier.ac.in/placements",
    },
    {"name": "Terna Engineering College", "city": "Mumbai", "placement_url": "https://ternaengg.ac.in/placements"},
    {
        "name": "SIES Graduate School of Technology",
        "city": "Mumbai",
        "placement_url": "https://siesgst.edu.in/placements",
    },
    {"name": "Lokmanya Tilak College of Engineering", "city": "Mumbai", "placement_url": "https://ltce.in/placements"},
    {"name": "Universal College of Engineering", "city": "Mumbai", "placement_url": "https://ucoe.edu.in/placements"},
    # Management / MBA Institutes
    {
        "name": "Jamnalal Bajaj Institute of Management Studies (JBIMS)",
        "city": "Mumbai",
        "placement_url": "https://jbims.edu/placements",
    },
    {
        "name": "S. P. Jain Institute of Management and Research (SPJIMR)",
        "city": "Mumbai",
        "placement_url": "https://spjimr.org/placements",
    },
    {
        "name": "NMIMS School of Business Management",
        "city": "Mumbai",
        "placement_url": "https://sbm.nmims.edu/placements",
    },
    {
        "name": "Prin. L. N. Welingkar Institute of Management (WeSchool)",
        "city": "Mumbai",
        "placement_url": "https://welingkar.org/placements",
    },
    {
        "name": "K. J. Somaiya Institute of Management",
        "city": "Mumbai",
        "placement_url": "https://simsr.somaiya.edu/placements",
    },
    {
        "name": "Sydenham Institute of Management (SIMSREE)",
        "city": "Mumbai",
        "placement_url": "https://simsree.org/placements",
    },
    {
        "name": "Chetana's R.K. Institute of Management and Research",
        "city": "Mumbai",
        "placement_url": "https://crkimr.in/placements",
    },
    {"name": "MET Institute of Management", "city": "Mumbai", "placement_url": "https://met.edu/placements"},
    {
        "name": "Lala Lajpatrai Institute of Management",
        "city": "Mumbai",
        "placement_url": "https://llim.edu/placements",
    },
    {
        "name": "SIES College of Management Studies",
        "city": "Mumbai",
        "placement_url": "https://siescoms.edu/placements",
    },
    # Arts, Science & Commerce Colleges
    {"name": "St. Xavier's College", "city": "Mumbai", "placement_url": "https://xaviers.edu/placements"},
    {"name": "Mithibai College", "city": "Mumbai", "placement_url": "https://mithibai.ac.in/placements"},
    {
        "name": "H.R. College of Commerce and Economics",
        "city": "Mumbai",
        "placement_url": "https://hrcollege.edu/placements",
    },
    {
        "name": "Narsee Monjee College of Commerce and Economics",
        "city": "Mumbai",
        "placement_url": "https://nmcollege.in/placements",
    },
    {"name": "K. C. College", "city": "Mumbai", "placement_url": "https://kccollege.edu.in/placements"},
    {"name": "Jai Hind College", "city": "Mumbai", "placement_url": "https://jaihindcollege.com/placements"},
    {
        "name": "R. A. Podar College of Commerce & Economics",
        "city": "Mumbai",
        "placement_url": "https://rapodar.ac.in/placements",
    },
    {
        "name": "Ramnarain Ruia Autonomous College",
        "city": "Mumbai",
        "placement_url": "https://ruiacollege.edu/placements",
    },
    {"name": "Wilson College", "city": "Mumbai", "placement_url": "https://wilsoncollege.edu/placements"},
    {
        "name": "Sophia College for Women",
        "city": "Mumbai",
        "placement_url": "https://sophiacollegemumbai.com/placements",
    },
]


# --- Mumbai Companies (~30) ---
MUMBAI_COMPANIES: List[Dict[str, Any]] = [
    # Global Capability Centers (GCCs)
    {"name": "Barclays Global Service Centre", "industry": "Banking & Financial Services", "category": "GCC"},
    {"name": "Morgan Stanley Advantage Services", "industry": "Investment Banking", "category": "GCC"},
    {"name": "JP Morgan Chase Global Technology", "industry": "Financial Technology", "category": "GCC"},
    {"name": "Citi GCC Mumbai", "industry": "Banking", "category": "GCC"},
    {"name": "Deutsche Bank DBOI Global Services", "industry": "Investment Banking", "category": "GCC"},
    {"name": "BNP Paribas India Solutions", "industry": "Banking & Finance", "category": "GCC"},
    {"name": "Nomura Services India", "industry": "Financial Services", "category": "GCC"},
    {"name": "UBS India Service Centre", "industry": "Wealth Management", "category": "GCC"},
    {"name": "Bank of America Continuum", "industry": "Banking & Tech", "category": "GCC"},
    {"name": "Macquarie Global Services", "industry": "Financial Services", "category": "GCC"},
    # Enterprises
    {"name": "Tata Consultancy Services", "industry": "Information Technology", "category": "enterprise"},
    {"name": "Reliance Industries", "industry": "Conglomerate & Telecom", "category": "enterprise"},
    {"name": "Larsen & Toubro", "industry": "Engineering & Technology", "category": "enterprise"},
    {"name": "Mahindra & Mahindra", "industry": "Automotive & Technology", "category": "enterprise"},
    {"name": "HDFC Bank", "industry": "Banking & Fintech", "category": "enterprise"},
    {"name": "ICICI Bank", "industry": "Banking & Financial Services", "category": "enterprise"},
    {"name": "Tata Motors", "industry": "Automotive", "category": "enterprise"},
    {"name": "Godrej Consumer Products", "industry": "FMCG", "category": "enterprise"},
    {"name": "Kotak Mahindra Bank", "industry": "Banking & Finance", "category": "enterprise"},
    {"name": "Aditya Birla Capital", "industry": "Financial Services", "category": "enterprise"},
    # Tech Startups / Scaleups
    {"name": "Zepto", "industry": "Quick Commerce", "category": "startup"},
    {"name": "BookMyShow", "industry": "Entertainment & Tech", "category": "startup"},
    {"name": "BrowserStack", "industry": "Cloud & Developer Tools", "category": "startup"},
    {"name": "Nykaa", "industry": "E-Commerce", "category": "startup"},
    {"name": "Upstox", "industry": "Fintech & Wealth", "category": "startup"},
    {"name": "Pepperfry", "industry": "E-Commerce", "category": "startup"},
    {"name": "Eruditus", "industry": "EdTech", "category": "startup"},
    {"name": "CleverTap", "industry": "SaaS & Analytics", "category": "startup"},
    {"name": "Rebel Foods", "industry": "FoodTech", "category": "startup"},
    {"name": "Gupshup", "industry": "Conversational AI & Messaging", "category": "startup"},
]


# --- Synthetic Contacts (~25) ---
MUMBAI_SYNTHETIC_CONTACTS: List[Dict[str, Any]] = [
    # Campus Recruiters & Talent Leaders at GCCs / Tech
    {
        "name": "Aarav Sharma",
        "title": "Lead Campus Recruiter",
        "company_name": "Tata Consultancy Services",
        "role_type": "campus_recruiter",
        "email": "aarav.sharma@tcs.example.com",
        "linkedin_url": "https://linkedin.com/in/aarav-sharma-recruiter-demo",
    },
    {
        "name": "Priya Nair",
        "title": "University Relations Manager",
        "company_name": "Barclays Global Service Centre",
        "role_type": "campus_recruiter",
        "email": "priya.nair@barclays.example.com",
        "linkedin_url": "https://linkedin.com/in/priya-nair-barclays-demo",
    },
    {
        "name": "Rohan Deshmukh",
        "title": "Campus Talent Lead",
        "company_name": "Morgan Stanley Advantage Services",
        "role_type": "campus_recruiter",
        "email": "rohan.deshmukh@morganstanley.example.com",
        "linkedin_url": "https://linkedin.com/in/rohan-deshmukh-ms-demo",
    },
    {
        "name": "Sneha Kulkarni",
        "title": "VP - Graduate Recruiting",
        "company_name": "JP Morgan Chase Global Technology",
        "role_type": "campus_recruiter",
        "email": "sneha.kulkarni@jpmchase.example.com",
        "linkedin_url": "https://linkedin.com/in/sneha-kulkarni-jpm-demo",
    },
    {
        "name": "Vikram Mehta",
        "title": "Director of University Hiring",
        "company_name": "BrowserStack",
        "role_type": "campus_recruiter",
        "email": "vikram.mehta@browserstack.example.com",
        "linkedin_url": "https://linkedin.com/in/vikram-mehta-browserstack-demo",
    },
    {
        "name": "Neha Joshi",
        "title": "Senior Technical Recruiter",
        "company_name": "Zepto",
        "role_type": "campus_recruiter",
        "email": "neha.joshi@zepto.example.com",
        "linkedin_url": "https://linkedin.com/in/neha-joshi-zepto-demo",
    },
    {
        "name": "Aditya Verma",
        "title": "HR Manager - Campus Initiatives",
        "company_name": "Larsen & Toubro",
        "role_type": "hr",
        "email": "aditya.verma@larsentoubro.example.com",
        "linkedin_url": "https://linkedin.com/in/aditya-verma-lt-demo",
    },
    {
        "name": "Pooja Hegde",
        "title": "Head of Early Careers",
        "company_name": "Reliance Industries",
        "role_type": "campus_recruiter",
        "email": "pooja.hegde@ril.example.com",
        "linkedin_url": "https://linkedin.com/in/pooja-hegde-ril-demo",
    },
    {
        "name": "Karan Singhania",
        "title": "Talent Acquisition Lead",
        "company_name": "HDFC Bank",
        "role_type": "hr",
        "email": "karan.singhania@hdfcbank.example.com",
        "linkedin_url": "https://linkedin.com/in/karan-singhania-hdfc-demo",
    },
    {
        "name": "Ananya Roy",
        "title": "Campus Hiring Specialist",
        "company_name": "Citi GCC Mumbai",
        "role_type": "campus_recruiter",
        "email": "ananya.roy@citi.example.com",
        "linkedin_url": "https://linkedin.com/in/ananya-roy-citi-demo",
    },
    {
        "name": "Siddharth Rao",
        "title": "Lead Tech Recruiter",
        "company_name": "CleverTap",
        "role_type": "recruiter",
        "email": "siddharth.rao@clevertap.example.com",
        "linkedin_url": "https://linkedin.com/in/siddharth-rao-clevertap-demo",
    },
    {
        "name": "Meera Patel",
        "title": "HR Business Partner",
        "company_name": "Godrej Consumer Products",
        "role_type": "hr",
        "email": "meera.patel@godrejcp.example.com",
        "linkedin_url": "https://linkedin.com/in/meera-patel-godrej-demo",
    },
    {
        "name": "Rahul Iyer",
        "title": "Senior Talent Partner",
        "company_name": "Deutsche Bank DBOI Global Services",
        "role_type": "campus_recruiter",
        "email": "rahul.iyer@db.example.com",
        "linkedin_url": "https://linkedin.com/in/rahul-iyer-db-demo",
    },
    {
        "name": "Divya Merchant",
        "title": "Campus Relations Lead",
        "company_name": "Nomura Services India",
        "role_type": "campus_recruiter",
        "email": "divya.merchant@nomura.example.com",
        "linkedin_url": "https://linkedin.com/in/divya-merchant-nomura-demo",
    },
    # Placement Cell Officers at Mumbai Colleges
    {
        "name": "Prof. Rajesh Patil",
        "title": "Training & Placement Officer",
        "college_name": "Veermata Jijabai Technological Institute (VJTI)",
        "role_type": "placement_officer",
        "email": "tpo@vjti.ac.in",
        "linkedin_url": "https://linkedin.com/in/prof-rajesh-patil-vjti-demo",
    },
    {
        "name": "Dr. Sunita Murthy",
        "title": "Head of Placements & Corporate Relations",
        "college_name": "Sardar Patel Institute of Technology (SPIT)",
        "role_type": "placement_officer",
        "email": "placements@spit.ac.in",
        "linkedin_url": "https://linkedin.com/in/dr-sunita-murthy-spit-demo",
    },
    {
        "name": "Prof. Amit Chawla",
        "title": "Training and Placement Officer",
        "college_name": "Dwarkadas J. Sanghvi College of Engineering (DJSCE)",
        "role_type": "placement_officer",
        "email": "tpo@djsce.ac.in",
        "linkedin_url": "https://linkedin.com/in/prof-amit-chawla-djsce-demo",
    },
    {
        "name": "Dr. Manisha Shinde",
        "title": "Placement Cell In-charge",
        "college_name": "Vivekanand Education Society Institute of Technology (VESIT)",
        "role_type": "placement_officer",
        "email": "placements@ves.ac.in",
        "linkedin_url": "https://linkedin.com/in/dr-manisha-shinde-vesit-demo",
    },
    {
        "name": "Prof. Sandeep Bansal",
        "title": "Head of Corporate Relations & Placements",
        "college_name": "Thadomal Shahani Engineering College (TSEC)",
        "role_type": "placement_officer",
        "email": "tpo@tsec.edu",
        "linkedin_url": "https://linkedin.com/in/prof-sandeep-bansal-tsec-demo",
    },
    {
        "name": "Dr. Kavita Kadam",
        "title": "Placement Officer",
        "college_name": "K. J. Somaiya College of Engineering (KJSCE)",
        "role_type": "placement_officer",
        "email": "placement.engg@somaiya.edu",
        "linkedin_url": "https://linkedin.com/in/dr-kavita-kadam-kjsce-demo",
    },
    {
        "name": "Prof. Vijay Wani",
        "title": "TPO - Engineering & Tech",
        "college_name": "Vidyalankar Institute of Technology (VIT)",
        "role_type": "placement_officer",
        "email": "placements@vit.edu.in",
        "linkedin_url": "https://linkedin.com/in/prof-vijay-wani-vit-demo",
    },
    {
        "name": "Prof. Hemant Kamat",
        "title": "Dean of Corporate Relations",
        "college_name": "Jamnalal Bajaj Institute of Management Studies (JBIMS)",
        "role_type": "placement_officer",
        "email": "cr@jbims.edu",
        "linkedin_url": "https://linkedin.com/in/prof-hemant-kamat-jbims-demo",
    },
    {
        "name": "Dr. Swati Kelkar",
        "title": "Career Cell Chairperson",
        "college_name": "St. Xavier's College",
        "role_type": "placement_officer",
        "email": "placement.cell@xaviers.edu",
        "linkedin_url": "https://linkedin.com/in/dr-swati-kelkar-xaviers-demo",
    },
    {
        "name": "Prof. Nimesh Parekh",
        "title": "Placement Coordinator",
        "college_name": "Narsee Monjee College of Commerce and Economics",
        "role_type": "placement_officer",
        "email": "placements@nmcollege.in",
        "linkedin_url": "https://linkedin.com/in/prof-nimesh-parekh-nm-demo",
    },
    {
        "name": "Dr. Archana Gokhale",
        "title": "Placement Convenor",
        "college_name": "Mithibai College",
        "role_type": "placement_officer",
        "email": "placements@mithibai.ac.in",
        "linkedin_url": "https://linkedin.com/in/dr-archana-gokhale-mithibai-demo",
    },
]


def seed_colleges(client: Client) -> Dict[str, str]:
    """
    Seeds Mumbai colleges idempotently by natural key (lower(name), lower(city)).
    Returns a dict mapping college name (lowercase) to its UUID.
    """
    college_map: Dict[str, str] = {}
    for item in MUMBAI_COLLEGES:
        name = item["name"].strip()
        city = item.get("city", "Mumbai").strip()

        # Check existing
        res = client.table("colleges").select("id, name, city").ilike("name", name).ilike("city", city).execute()
        if res.data and len(res.data) > 0:
            cid = str(res.data[0]["id"])
            college_map[name.lower()] = cid
        else:
            cid = str(uuid.uuid4())
            new_row = {
                "id": cid,
                "name": name,
                "city": city,
            }
            ins = client.table("colleges").insert(new_row).execute()
            if ins.data and len(ins.data) > 0:
                cid = str(ins.data[0].get("id", cid))
            college_map[name.lower()] = cid

    return college_map


def seed_companies(client: Client) -> Dict[str, str]:
    """
    Seeds Mumbai companies idempotently by natural key lower(name).
    Returns a dict mapping company name (lowercase) to its UUID.
    """
    company_map: Dict[str, str] = {}
    for item in MUMBAI_COMPANIES:
        name = item["name"].strip()
        industry = item.get("industry")
        category = item.get("category")

        res = client.table("companies").select("id, name").ilike("name", name).execute()
        if res.data and len(res.data) > 0:
            cid = str(res.data[0]["id"])
            # Update category/industry if needed
            client.table("companies").update({"category": category, "industry": industry}).eq("id", cid).execute()
            company_map[name.lower()] = cid
        else:
            cid = str(uuid.uuid4())
            new_row = {
                "id": cid,
                "name": name,
                "industry": industry,
                "category": category,
            }
            ins = client.table("companies").insert(new_row).execute()
            if ins.data and len(ins.data) > 0:
                cid = str(ins.data[0].get("id", cid))
            company_map[name.lower()] = cid

    return company_map


def seed_contacts(
    client: Client,
    company_map: Dict[str, str],
    college_map: Dict[str, str],
) -> List[str]:
    """
    Seeds synthetic Mumbai contacts idempotently.
    Attaches provenance in contact_sources (source='seed', note='synthetic').
    Returns a list of seeded contact IDs.
    """
    contact_ids: List[str] = []
    for item in MUMBAI_SYNTHETIC_CONTACTS:
        name = item["name"].strip()
        title = item.get("title")
        role_type = item.get("role_type", "other")
        email = item.get("email", "").strip().lower() if item.get("email") else None
        linkedin_url = item.get("linkedin_url", "").strip().lower() if item.get("linkedin_url") else None

        company_id: Optional[str] = None
        if item.get("company_name"):
            company_id = company_map.get(item["company_name"].strip().lower())

        college_id: Optional[str] = None
        if item.get("college_name"):
            college_id = college_map.get(item["college_name"].strip().lower())

        # Check existing contact
        existing = None
        if linkedin_url:
            q = client.table("contacts").select("id").ilike("linkedin_url", linkedin_url).execute()
            if q.data and len(q.data) > 0:
                existing = q.data[0]
        if not existing and email:
            q = client.table("contacts").select("id").ilike("email", email).execute()
            if q.data and len(q.data) > 0:
                existing = q.data[0]
        if not existing and name and company_id:
            q = client.table("contacts").select("id").eq("company_id", company_id).ilike("name", name).execute()
            if q.data and len(q.data) > 0:
                existing = q.data[0]

        contact_payload = {
            "name": name,
            "title": title,
            "role_type": role_type,
            "email": email,
            "linkedin_url": linkedin_url,
            "company_id": company_id,
            "college_id": college_id,
            "source": "seed",
            "confidence": 1.0,
        }

        if existing:
            contact_id = str(existing["id"])
            client.table("contacts").update(contact_payload).eq("id", contact_id).execute()
        else:
            contact_id = str(uuid.uuid4())
            contact_payload["id"] = contact_id
            ins = client.table("contacts").insert(contact_payload).execute()
            if ins.data and len(ins.data) > 0:
                contact_id = str(ins.data[0].get("id", contact_id))

        contact_ids.append(contact_id)

        # Upsert provenance in contact_sources
        src_res = (
            client.table("contact_sources").select("id").eq("contact_id", contact_id).eq("source", "seed").execute()
        )
        if not (src_res.data and len(src_res.data) > 0):
            client.table("contact_sources").insert(
                {
                    "id": str(uuid.uuid4()),
                    "contact_id": contact_id,
                    "source": "seed",
                    "source_url": linkedin_url or email,
                    "confidence": 1.0,
                    "unverified": False,
                    "note": "synthetic",
                }
            ).execute()

    return contact_ids


def seed_data(client: Client) -> Dict[str, Any]:
    """
    Top-level idempotent seed function.
    Can be run repeatedly without duplicating rows.
    Loads from data/seed/*.csv if present, falling back to python lists.
    Covers colleges, companies, college_domains, and sample contacts.
    Returns counts and report.
    """
    logger.info("Starting idempotent seed for shared lake...")
    try:
        from scripts.seed_csv_data import seed_all_csvs

        csv_report = seed_all_csvs(client)
        summary = {
            "colleges": csv_report["colleges"]["added"] + csv_report["colleges"]["matched"],
            "companies": csv_report["companies"]["added"] + csv_report["companies"]["matched"],
            "contacts": csv_report["contacts"]["added"] + csv_report["contacts"]["matched"],
        }
        logger.info(f"Seed complete via CSV: {summary}")
        return summary
    except Exception as exc:
        logger.warning(f"CSV loader failed or not available ({exc}), falling back to internal list seed.")
        colleges = seed_colleges(client)
        companies = seed_companies(client)
        contacts = seed_contacts(client, companies, colleges)
        summary = {
            "colleges": len(colleges),
            "companies": len(companies),
            "contacts": len(contacts),
        }
        logger.info(f"Seed complete: {summary}")
        return summary
