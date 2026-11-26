"""Fake posts (written by me, NOT real club posts) used by `python -m pipeline.run --demo`
to test the extractor and preview the website. Dates are generated relative to today."""
from datetime import timedelta
from .models import Post

FR_MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def make(now):
    md = lambda n: f"{(now + timedelta(days=n)).strftime('%B')} {(now + timedelta(days=n)).day}"
    fr = lambda n: f"{(now + timedelta(days=n)).day} {FR_MONTHS[(now + timedelta(days=n)).month - 1]}"
    soon = (now + timedelta(minutes=95)).strftime("%I:%M %p").lstrip("0")
    P = lambda h, i, cap, hrs_ago: Post("instagram", h, i, f"https://www.instagram.com/p/{i}/", cap, now - timedelta(hours=hrs_ago), [], "")
    return [
        P("uo.ebc", "D1", f"Resume Workshop 🎓 | Atelier de CV\n📅 {md(3)}\n🕕 6-8 PM\n📍 STM 464\nFree! Gratuit! Register / Inscrivez-vous via the link in our bio. Join us for tips on your CV. Venez nous voir pour des conseils sur votre CV.", 24),
        P("ieeeuottawa", "D2", "Weekly Coding Night 💻\nEvery Thursday 7-9pm in CBY B205\nNo RSVP needed - drop-in! Bring your laptop and join the fun. Everyone is welcome to come and code with us.", 30),
        P("tsa.uottawa", "D3", f"Soirée de jeux 🎲\nRejoignez-nous le {fr(5)} à 19h30 au local UCU 202! Gratuit pour tous. Venez nous voir et amenez vos amis!", 40),
        P("uo.bsa", "D4", f"Panel discussion: Careers in public service\n{md(8)} 5:30 PM at Tabaret Hall. English only. $5 for non-members, free for members. RSVP required.", 50),
        P("genie_engineering_uottawa", "D5", f"Intramural Soccer Registration 🏆\nRegister by {md(6)}! Sign up at the link in our bio. $20 per team. Come and join us this winter.", 20),
        P("uo.ebc", "D6", f"Update: the CV workshop on {md(3)} has been cancelled. Sorry!", 2),
        P("ieeeuottawa", "D7", "Room change: this Thursday's coding night is now in CBY B101.", 1),
        P("uomsa.aemuo", "D8", f"Friday Q&A session 🕌\n{md(2)} at 1pm, UCU 207. Free. Everyone is welcome to join us.", 26),
        P("food_bank_aliment", "D9", f"Community fridge pickup 🍎\n{md(-3)} 12-2 pm at UCU. Free! Come and get fresh food for the week.", 6 * 24),
        P("mtlbsauo", "D10", f"Save the date! Our annual gala is on {md(20)}. More details soon, join us for this big event!", 5),
        P("uo_ysa", "D11", f"Old event recap {md(-20)} at 6pm in UCU 101. Thank you to everyone who came!", 20 * 24),
        P("uo_ysa", "D12", "Thank you to everyone who came out, you are the best!", 3),
        P("uottawa_essaeg", "D13", f"Study session tonight {soon} @ MRT 252. Free pizza 🍕 Come and study with us, the exams are near!", 1),
        P("rwsa.uottawa", "D14", f"Cooking Workshop 1 of 2: {md(-2)} at 6pm in UCU 202. Learn to cook with us and join our team!", 4 * 24),
        P("rwsa.uottawa", "D15", f"Cooking Workshop 2 of 2: {md(4)} at 6pm in UCU 202. Learn to cook with us and join our team!", 4 * 24 - 1),
    ]
