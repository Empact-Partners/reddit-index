#!/usr/bin/env python3
"""Reddit Index — the authoritative brand list and alias table.

`brand-gazetteer-seed.csv` uses a THIRD category vocabulary. Its 17 labels match
neither `categories.csv` nor `category-tests-20.csv`; two of them (`Application
Development`, `Workflow Management`) have no category row at all; and five of
the twenty measured categories have no gazetteer brands whatsoever. Joining
brands to categories needs a hand-written map, and this file is it.

Two outputs, both regenerated, never hand-edited:

  data/brands.csv         one row per brand, globally unique, with its primary
                          category, domains, and per-brand disambiguation rules
  data/brand-aliases.csv  one row per SURFACE FORM

The alias split matters. 05-entity-resolution.md §5: "Treat every surface form
as its own row with its own learned precision prior. A surface form is never
simply an alias that inherits the brand's confidence." `monday.com` and bare
`monday` are the same brand and nothing like the same evidence.

Surface-form classes, from the gazetteer's `ambiguity_class`:
  SAFE       accept on a word-boundary match
  AMBIGUOUS  accept only with >=1 corroborating signal
  HOSTILE    accept only with >=2 corroborating signals AND no stop-context hit

and one class the gazetteer has no word for:
  bare_disabled  the bare token is never matchable at any score. Reserved for
                 words so common that no stop-context list reaches the published
                 precision bar - `close`, `make`, `front`, `square`, `render`,
                 `motion`, `craft`. Those brands resolve only through a
                 qualified form (`close.com`, `Close CRM`). The recall loss is
                 real, it is per-brand, and it is published rather than hidden.
"""
import csv, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def slugify(s):
    s = s.lower().replace("&", " and ").replace(".", " ").replace("+", " plus ")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return re.sub(r"-+", "-", s)


# ── gazetteer label -> the 20 measured category slugs ────────────────────────
# HANDOFF.md item 4: no crosswalk between the two taxonomies ships, and only 8
# join exactly. This is that crosswalk, for the 20 measured categories only.
LABEL_TO_SLUG = {
    "CRM": "crm",
    "Project Management": "project-management",
    "Accounting": "accounting",
    "Human Resources": "hr",
    "Email Marketing": "email-marketing",
    "Marketing Automation": "marketing-automation",
    "Password Managers / Security": "password-managers",
    "Note-taking / Knowledge Mgmt": "note-taking",
    "Design / Prototyping": "design",
    "Video Editing": "video-editing",
    "Help Desk / Support": "help-desk",
    "ERP": "erp",
    "Data Analysis": "business-intelligence",
    "eCommerce": "ecommerce",
    "Collaboration": "team-chat",
    # Vercel, Netlify, Heroku, Render, Railway, Supabase are hosting, not a
    # category of their own in the measured twenty.
    "Application Development": "cloud-hosting",
    # Zapier, Make, n8n, Airtable, Retool are iPaaS / low-code. No measured
    # category covers them and forcing them into Marketing Automation would be
    # a taxonomy error, so they are OUT of v1 and recorded in HANDOFF.md.
    "Workflow Management": None,
}

# ── brands the gazetteer never had ──────────────────────────────────────────
# Five measured categories ship with zero gazetteer coverage. Seed brands come
# from `category-candidates-20.json`, which is the list the subreddit study
# actually measured against, so using them keeps the instrument consistent.
# (brand, category_slug, aliases, ambiguity_class, note)
ADDITIONS = [
    # Applicant Tracking and Recruiting
    ("Greenhouse", "recruiting", ["Greenhouse.io"], "high", "'greenhouse' is a common English noun"),
    ("Lever", "recruiting", ["Lever.co"], "high", "'lever' is a common English noun"),
    ("Workable", "recruiting", [], "high", "'workable' is a common English adjective"),
    ("Ashby", "recruiting", ["AshbyHQ"], "medium", "also a surname and an English place name"),
    ("Recruitee", "recruiting", [], "low", ""),
    ("SmartRecruiters", "recruiting", [], "low", ""),
    ("Lokala", "recruiting", [], "low", ""),
    # Payroll
    ("Paychex", "payroll", [], "low", ""),
    ("Justworks", "payroll", [], "low", ""),
    ("Remote", "payroll", ["Remote.com"], "high", "'remote' is an extremely common English word"),
    ("OnPay", "payroll", [], "medium", "'on pay' occurs as an ordinary phrase"),
    ("Papaya Global", "payroll", ["Papaya"], "medium", "'papaya' is a common noun"),
    # Cloud Hosting and Infrastructure
    ("DigitalOcean", "cloud-hosting", ["Digital Ocean", "DO droplet"], "low", ""),
    ("Linode", "cloud-hosting", ["Akamai Linode"], "low", ""),
    ("Hetzner", "cloud-hosting", [], "low", ""),
    ("Cloudflare", "cloud-hosting", ["Cloudflare Pages"], "low", ""),
    ("Fly.io", "cloud-hosting", ["Flyio"], "medium", "'fly' is a common English verb"),
    # Backup and Storage
    ("Backblaze", "backup-storage", ["B2"], "low", ""),
    ("Dropbox", "backup-storage", [], "low", ""),
    ("Google Drive", "backup-storage", ["GDrive"], "medium", "'Drive' alone is far too common to match"),
    ("Synology", "backup-storage", [], "low", ""),
    ("Veeam", "backup-storage", [], "low", ""),
    ("pCloud", "backup-storage", [], "low", ""),
    ("Wasabi", "backup-storage", [], "high", "'wasabi' is a common food noun"),
    # Payment Processing
    ("PayPal", "payment-processing", [], "low", ""),
    ("Square", "payment-processing", ["Block Square"], "high", "'square' is an extremely common English word"),
    ("Adyen", "payment-processing", [], "low", ""),
    ("Braintree", "payment-processing", [], "medium", "also a US place name"),
    ("Mollie", "payment-processing", [], "high", "'Mollie' is a common given name"),
    ("Checkout.com", "payment-processing", ["Checkout com"], "medium", "'checkout' is ordinary commerce vocabulary"),
    # gaps in categories that DO have gazetteer coverage
    ("Attio", "crm", [], "low", ""),
    ("Sage", "accounting", ["Sage Accounting"], "high", "'sage' is a herb and an adjective"),
    ("Wave", "accounting", ["Wave Accounting"], "high", "'wave' is a common English word"),
    ("ConvertKit", "email-marketing", ["Kit"], "low", ""),
    ("Customer.io", "marketing-automation", ["Customerio"], "medium", "reads as the ordinary phrase 'customer io'"),
    ("Metabase", "business-intelligence", [], "low", ""),
    ("Discord", "team-chat", [], "high", "'discord' is a common English noun, and the app is named constantly outside software evaluation"),
    ("Zoom", "team-chat", [], "high", "'zoom' is a common English verb"),
    ("Google Meet", "team-chat", ["GMeet"], "medium", "'Meet' alone is far too common to match"),
]

# Bare tokens no stop-context list can rescue. These brands resolve ONLY through
# a qualified surface form. 05-entity-resolution.md §9: excluded, not guessed.
BARE_DISABLED = {
    "close", "make", "front", "square", "render", "motion", "craft", "remote",
    "bob", "wave", "lever", "resolve", "b2", "kit", "do droplet",
}

# Brand -> the domains that auto-accept it. The strongest signal in 05 §4:
# "Auto-accept, near-zero false positives." Written by hand; a wrong domain is
# worse than a missing one.
DOMAINS = {
    "Salesforce": ["salesforce.com", "force.com"], "HubSpot": ["hubspot.com"],
    "Zoho CRM": ["crm.zoho.com", "zoho.com/crm"], "monday CRM": ["monday.com"],
    "Pipedrive": ["pipedrive.com"], "Bitrix24": ["bitrix24.com"],
    "NetSuite": ["netsuite.com"], "Close": ["close.com", "close.io"],
    "Freshsales": ["freshsales.io", "freshworks.com/crm"], "Attio": ["attio.com"],
    "monday.com": ["monday.com"], "Asana": ["asana.com"], "Jira": ["atlassian.com/software/jira"],
    "Wrike": ["wrike.com"], "Smartsheet": ["smartsheet.com"], "ClickUp": ["clickup.com"],
    "Trello": ["trello.com"], "Basecamp": ["basecamp.com"], "Notion": ["notion.so", "notion.com"],
    "Linear": ["linear.app"], "Slack": ["slack.com"], "Microsoft Teams": ["teams.microsoft.com"],
    "Confluence": ["atlassian.com/software/confluence"], "Miro": ["miro.com"],
    "Google Workspace": ["workspace.google.com"], "Discord": ["discord.com", "discord.gg"],
    "Zoom": ["zoom.us"], "Google Meet": ["meet.google.com"],
    "BambooHR": ["bamboohr.com"], "Rippling": ["rippling.com"], "Gusto": ["gusto.com"],
    "Workday": ["workday.com"], "HiBob": ["hibob.com"], "Paylocity": ["paylocity.com"],
    "Paycom": ["paycom.com"], "Deel": ["deel.com"], "ADP": ["adp.com"],
    "Paychex": ["paychex.com"], "Justworks": ["justworks.com"], "Remote": ["remote.com"],
    "OnPay": ["onpay.com"], "Papaya Global": ["papayaglobal.com"],
    "QuickBooks": ["quickbooks.intuit.com"], "Xero": ["xero.com"], "FreshBooks": ["freshbooks.com"],
    "Chargebee": ["chargebee.com"], "Stripe": ["stripe.com"], "Bill.com": ["bill.com"],
    "Melio": ["meliopayments.com"], "Ramp": ["ramp.com"], "Brex": ["brex.com"],
    "Sage": ["sage.com"], "Wave": ["waveapps.com"],
    "HubSpot Marketing Hub": ["hubspot.com/products/marketing"], "Marketo Engage": ["marketo.com"],
    "ActiveCampaign": ["activecampaign.com"], "Klaviyo": ["klaviyo.com"],
    "Customer.io": ["customer.io"], "Mailchimp": ["mailchimp.com"], "Braze": ["braze.com"],
    "Constant Contact": ["constantcontact.com"], "Beehiiv": ["beehiiv.com"],
    "ConvertKit": ["convertkit.com", "kit.com"],
    "Figma": ["figma.com"], "Sketch": ["sketch.com"], "Adobe XD": ["adobe.com/products/xd"],
    "Canva": ["canva.com"], "Framer": ["framer.com"], "Webflow": ["webflow.com"],
    "Bitwarden": ["bitwarden.com"], "1Password": ["1password.com"], "LastPass": ["lastpass.com"],
    "Dashlane": ["dashlane.com"], "Proton Pass": ["proton.me/pass"], "KeePass": ["keepass.info"],
    "NordPass": ["nordpass.com"],
    "Obsidian": ["obsidian.md"], "Evernote": ["evernote.com"], "OneNote": ["onenote.com"],
    "Logseq": ["logseq.com"], "Anytype": ["anytype.io"], "Roam Research": ["roamresearch.com"],
    "Craft": ["craft.do"],
    "Zendesk": ["zendesk.com"], "Freshdesk": ["freshdesk.com"], "Intercom": ["intercom.com"],
    "Front": ["frontapp.com", "front.com"], "Help Scout": ["helpscout.com"],
    "ServiceNow": ["servicenow.com"],
    "SAP": ["sap.com"], "Odoo": ["odoo.com"], "Sage Intacct": ["intacct.com"],
    "Microsoft Dynamics 365": ["dynamics.microsoft.com"], "Acumatica": ["acumatica.com"],
    "Shopify": ["shopify.com"], "WooCommerce": ["woocommerce.com"],
    "BigCommerce": ["bigcommerce.com"], "Squarespace": ["squarespace.com"], "Wix": ["wix.com"],
    "Tableau": ["tableau.com"], "Power BI": ["powerbi.microsoft.com"], "Looker": ["looker.com"],
    "Qlik": ["qlik.com"], "Amplitude": ["amplitude.com"], "Mixpanel": ["mixpanel.com"],
    "Segment": ["segment.com"], "Metabase": ["metabase.com"],
    "Vercel": ["vercel.com"], "Netlify": ["netlify.com"], "Heroku": ["heroku.com"],
    "Render": ["render.com"], "Railway": ["railway.app", "railway.com"], "Supabase": ["supabase.com"],
    "DigitalOcean": ["digitalocean.com"], "Linode": ["linode.com"], "Hetzner": ["hetzner.com"],
    "Cloudflare": ["cloudflare.com"], "Fly.io": ["fly.io"],
    "Backblaze": ["backblaze.com"], "Dropbox": ["dropbox.com"],
    "Google Drive": ["drive.google.com"], "Synology": ["synology.com"], "Veeam": ["veeam.com"],
    "pCloud": ["pcloud.com"], "Wasabi": ["wasabi.com"],
    "PayPal": ["paypal.com"], "Square": ["squareup.com"], "Adyen": ["adyen.com"],
    "Braintree": ["braintreepayments.com"], "Mollie": ["mollie.com"],
    "Checkout.com": ["checkout.com"],
    "Loom": ["loom.com"], "Descript": ["descript.com"], "CapCut": ["capcut.com"],
    "DaVinci Resolve": ["blackmagicdesign.com/products/davinciresolve"],
    "Final Cut Pro": ["apple.com/final-cut-pro"],
    "Premiere Pro": ["adobe.com/products/premiere"], "Motion": ["apple.com/final-cut-pro/motion"],
}

# Negative contexts. A hit inside the match window is a hard reject: the word is
# being used in its ordinary English sense, not as a product name. Measured
# false matches recorded in 05-entity-resolution.md §3 seed this list.
STOP_CONTEXTS = {
    "monday CRM": ["on monday", "next monday", "last monday", "this monday", "every monday",
                   "monday morning", "monday afternoon", "monday night", "monday evening",
                   "monday through friday", "monday to friday", "mon-fri", "by monday",
                   "until monday", "since monday", "mondays", "cyber monday", "blue monday",
                   "monday night football", "bank holiday monday", "tuesday", "wednesday",
                   "thursday", "friday", "saturday", "sunday"],
    "monday.com": ["on monday", "next monday", "last monday", "this monday", "every monday",
                   "monday morning", "monday through friday", "mon-fri", "mondays",
                   "cyber monday", "tuesday", "wednesday", "thursday", "friday"],
    "Close": ["close the deal", "closed won", "closed lost", "close rate", "closing",
              "close to", "too close", "so close", "very close", "pretty close", "not close",
              "close enough", "close call", "up close", "close it", "close out",
              "close the ticket", "close the tab", "close the account", "market close"],
    "Notion": ["the notion that", "notion of", "no notion", "any notion", "notions",
               "romantic notion", "vague notion", "preconceived notion"],
    "Slack": ["slack off", "slacking", "picked up the slack", "pick up the slack",
              "cut me some slack", "cut some slack", "slack in the rope", "slack jaw"],
    "Linear": ["linear regression", "linear algebra", "linear equation", "linear time",
               "linear model", "linear scale", "linear relationship", "linearly",
               "non-linear", "nonlinear", "linear fashion"],
    "Stripe": ["pinstripe", "racing stripe", "stripe of", "stripes", "striped"],
    "Ramp": ["on-ramp", "off-ramp", "ramp up", "ramp down", "ramping", "wheelchair ramp",
             "loading ramp", "ramp period"],
    "Make": ["make sure", "make a", "make it", "make the", "makes", "making", "made",
             "make sense", "make money", "make do", "make up"],
    "Front": ["in front", "up front", "front end", "front-end", "front of", "storefront",
              "front door", "front page", "front line", "front desk", "waterfront"],
    "Segment": ["customer segment", "market segment", "segment of", "segments", "segmentation",
                "audience segment", "user segment"],
    "Amplitude": ["amplitude of", "wave amplitude", "signal amplitude", "peak amplitude"],
    "Looker": ["good looker", "nice looker", "lookers"],
    "Render": ["render a", "rendering", "rendered", "3d render", "render farm", "render time",
               "render engine", "renders"],
    "Railway": ["railway station", "railway line", "railway company", "railways",
                "railway track", "national railway"],
    "Motion": ["in motion", "slow motion", "motion blur", "motion graphics", "range of motion",
               "motion sensor", "motion to", "motions", "motion sickness"],
    "Craft": ["craft beer", "craft a", "crafting", "crafted", "handcraft", "witchcraft",
              "aircraft", "spacecraft", "craftsmanship", "crafts"],
    "Sketch": ["sketch out", "sketchy", "quick sketch", "sketches", "sketching", "sketch comedy",
               "rough sketch"],
    "Framer": ["framer motion"],  # the animation library, a different product
    "Sage": ["sage advice", "sage green", "sage leaves", "burning sage", "sage brush",
             "sagebrush", "wise sage", "sage and onion"],
    "Gusto": ["with gusto", "gusto for", "ate with gusto"],
    "Rippling": ["rippling water", "rippling muscles", "rippling effect", "rippling through",
                 "ripples"],
    "Workday": ["long workday", "the workday", "during the workday", "workdays",
                "end of the workday", "a workday"],
    "Discord": ["discord between", "sowing discord", "sow discord", "in discord",
                "discord among", "marital discord"],
    "Zoom": ["zoom in", "zoom out", "zoomed", "zooming", "zoom lens", "zoom level"],
    "Square": ["square footage", "square feet", "square meter", "square metre", "town square",
               "square one", "fair and square", "square root", "square peg", "square away",
               "squares", "times square"],
    "Remote": ["remote work", "remote job", "remote team", "remote first", "fully remote",
               "work remote", "remote control", "remote location", "remotely", "remote server"],
    "Wave": ["wave of", "new wave", "heat wave", "brain wave", "sound wave", "waves",
             "wave goodbye", "microwave", "shockwave"],
    "Lever": ["lever to", "leverage", "leveraging", "levers", "pull the lever", "lever arm"],
    "Greenhouse": ["greenhouse gas", "greenhouse effect", "greenhouse emissions",
                   "a greenhouse", "greenhouses", "greenhouse tomatoes"],
    "Workable": ["workable solution", "workable plan", "not workable", "a workable",
                 "workable compromise"],
    "Wasabi": ["wasabi peas", "wasabi sauce", "soy and wasabi", "wasabi paste"],
    "Mollie": ["mollie is", "hi mollie", "mollie's"],
    "Resolve": ["resolve to", "resolve the", "resolved", "resolving", "new year's resolution",
                "conflict resolve"],
    "Bill.com": ["the bill", "a bill", "bills", "bill for", "electric bill", "phone bill",
                 "bill of", "billed", "billing"],
    "HiBob": ["hi bob", "hey bob", "bob's", "bob said", "uncle bob"],
    "Papaya Global": ["papaya fruit", "papaya salad", "eat papaya"],
    "Fly.io": ["fly to", "flying", "fly out", "fly by", "fruit fly", "on the fly"],
}


def main():
    cats = {r["slug"]: r["category"] for r in
            csv.DictReader(open(os.path.join(HERE, "categories.csv")))}

    seen, brands, dropped = {}, [], []
    for row in csv.DictReader(open(os.path.join(HERE, "brand-gazetteer-seed.csv"))):
        slug_cat = LABEL_TO_SLUG.get(row["category"], "__unmapped__")
        if slug_cat is None:
            dropped.append((row["brand"], row["category"]))
            continue
        if slug_cat == "__unmapped__":
            raise SystemExit(f"gazetteer label with no crosswalk entry: {row['category']!r}")
        key = row["brand"].lower()
        if key in seen:
            # NetSuite (CRM + ERP) and Notion (PM + note-taking) ship twice. One
            # brand is one row; the FIRST category is its primary. A brand still
            # scores in every category it is mentioned in - the score grain is
            # (brand x category) and comes from where the mention was found.
            seen[key]["also_in"].append(slug_cat)
            continue
        rec = {
            "brand": row["brand"],
            "primary_category_slug": slug_cat,
            "aliases": [a for a in (row.get("aliases") or "").split(";") if a],
            "ambiguity_class": row["ambiguity_class"],
            "ambiguity_note": row.get("ambiguity_note", ""),
            "also_in": [],
            "source": "gazetteer",
        }
        seen[key] = rec
        brands.append(rec)

    for brand, cat, aliases, amb, note in ADDITIONS:
        key = brand.lower()
        if key in seen:
            raise SystemExit(f"ADDITIONS duplicates a gazetteer brand: {brand}")
        if cat not in cats:
            raise SystemExit(f"ADDITIONS references an unknown category slug: {cat}")
        rec = {"brand": brand, "primary_category_slug": cat, "aliases": list(aliases),
               "ambiguity_class": amb, "ambiguity_note": note, "also_in": [],
               "source": "seed-brands"}
        seen[key] = rec
        brands.append(rec)

    # ── the fleet-enumerated seed for the expansion categories ──────────────
    # data/brand-seed-new.csv is produced by data/enumerate_brands.py (fleet
    # draft -> adversarial review -> deterministic gates). The hand dicts above
    # stay the frozen source for the original 145 — this loader only APPENDS,
    # and for an already-known brand only widens also_in.
    # brand-seed-expand.csv is the SAME contract from the uncapped depth
    # expansion (enumerate_brands.py --expand) and loads through the same
    # append-only rules, after seed-new so earlier layers keep priority.
    seed_files = [os.path.join(HERE, "brand-seed-new.csv"),
                  os.path.join(HERE, "brand-seed-expand.csv")]
    for new_fp in [fp for fp in seed_files if os.path.exists(fp)]:
        for row in csv.DictReader(open(new_fp)):
            key = row["brand"].lower()
            row_cats = [row["primary_category_slug"]] + [
                c for c in (row.get("also_in_category_slugs") or "").split(";") if c]
            for c in row_cats:
                if c not in cats:
                    raise SystemExit(f"brand-seed-new references unknown category: {c}")
            if key in seen:
                rec = seen[key]
                for c in row_cats:
                    if c != rec["primary_category_slug"] and c not in rec["also_in"]:
                        rec["also_in"].append(c)
                continue
            rec = {
                "brand": row["brand"],
                "primary_category_slug": row_cats[0],
                "aliases": [a for a in (row.get("aliases") or "").split(";") if a],
                "ambiguity_class": row["ambiguity_class"],
                "ambiguity_note": row.get("ambiguity_note", ""),
                "also_in": row_cats[1:],
                "source": row.get("source") or "fleet-enum",
                "_domains": [d for d in (row.get("domains") or "").split(";") if d],
                "_stops": [x for x in (row.get("stop_contexts") or "").split(";") if x],
                "_bare": {x.lower() for x in (row.get("bare_disabled_forms") or "").split(";") if x},
            }
            seen[key] = rec
            brands.append(rec)

    CLASS = {"low": "SAFE", "medium": "AMBIGUOUS", "high": "HOSTILE"}
    MIN_CORROB = {"SAFE": 0, "AMBIGUOUS": 1, "HOSTILE": 2}

    brand_rows, alias_rows = [], []
    for b in brands:
        s = slugify(b["brand"])
        doms = b.get("_domains") or DOMAINS.get(b["brand"], [])
        stops = b.get("_stops") or STOP_CONTEXTS.get(b["brand"], [])
        cls = CLASS[b["ambiguity_class"]]
        brand_rows.append({
            "brand": b["brand"],
            "slug": s,
            "primary_category_slug": b["primary_category_slug"],
            "also_in_category_slugs": ";".join(sorted(set(b["also_in"]))),
            "ambiguity_class": b["ambiguity_class"],
            "surface_class": cls,
            "require_context": cls != "SAFE",
            "min_corroborating": MIN_CORROB[cls],
            "domains": ";".join(doms),
            "stop_contexts": ";".join(stops),
            "ambiguity_note": b["ambiguity_note"],
            "source": b["source"],
        })

        forms = [(b["brand"], cls)] + [(a, cls) for a in b["aliases"]]
        for dom in doms:
            forms.append((dom, "SAFE"))  # a URL is auto-accept evidence
        emitted = set()
        for form, fcls in forms:
            fkey = form.lower()
            if fkey in emitted:
                continue
            emitted.add(fkey)
            # A qualified form inherits nothing from the bare token's ambiguity:
            # `Close CRM` and `close.com` are unambiguous, `close` is not.
            qualified = ("." in form) or (len(form.split()) > 1)
            eff = "SAFE" if qualified else fcls
            disabled = (not qualified) and (fkey in BARE_DISABLED or fkey in b.get("_bare", set()))
            alias_rows.append({
                "brand_slug": s,
                "alias": form,
                "alias_type": "domain" if "." in form and " " not in form else
                              ("canonical" if form == b["brand"] else "alias"),
                "surface_class": eff,
                "min_corroborating": MIN_CORROB[eff],
                "bare_disabled": disabled,
            })

    for name, rows, cols in [
        ("brands.csv", brand_rows,
         ["brand", "slug", "primary_category_slug", "also_in_category_slugs", "ambiguity_class",
          "surface_class", "require_context", "min_corroborating", "domains", "stop_contexts",
          "ambiguity_note", "source"]),
        ("brand-aliases.csv", alias_rows,
         ["brand_slug", "alias", "alias_type", "surface_class", "min_corroborating", "bare_disabled"]),
    ]:
        p = os.path.join(HERE, name)
        with open(p + ".tmp", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        os.replace(p + ".tmp", p)
        print(f"wrote data/{name}  ({len(rows)} rows)")

    per_cat = {}
    for r in brand_rows:
        per_cat.setdefault(r["primary_category_slug"], []).append(r["brand"])
    print(f"\n{len(brand_rows)} brands, {len(alias_rows)} surface forms")
    print(f"dropped (no measured category): {[b for b, _ in dropped]}")
    thin = []
    for slug, name in cats.items():
        n = len(per_cat.get(slug, []))
        if n < 4:
            thin.append(slug)
        print(f"  {slug:24}{n:>3}  {', '.join(sorted(per_cat.get(slug, []))[:7])}")
    disabled = sum(1 for a in alias_rows if a["bare_disabled"])
    print(f"\nbare-disabled surface forms: {disabled}")
    print(f"categories with a brand list too thin to fit a prior (<4): {thin or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
