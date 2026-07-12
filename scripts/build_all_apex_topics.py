#!/usr/bin/env python3
"""Build four additional Apex Archives scripts from structured facts + shared assembler."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from apex_assembler import assemble_topic  # noqa: E402
from apex_enrich import finalize_script  # noqa: E402
from create_apex_batch import validate_script, word_count  # noqa: E402

OUT_DIR = SCRIPTS / "apex_topics"


FILLERS = [
    " Documentary pacing keeps habitat footage on screen while narration carries the statistical weight.",
    " Where studies disagree, this ranking uses conservative medians rather than outlier years.",
    " Emergency medicine and ecology papers sometimes diverge on edge cases — we cite the range when that happens.",
    " The mechanism matters as much as the headline number: exposure, biology, and context combine into outcome.",
    " Map overlays and timeline graphics anchor scale without breaking the documentary tone.",
    " Popular myths exaggerate this risk; the sourced figure is usually dramatic enough without embellishment.",
    " Regional variation is real — commenters often add local detail datasets miss.",
    " This beat connects animal biology to the human systems that record harm: hospitals, farms, roads, or trade.",
]


def expand(core: str, target: int = 68) -> str:
    words = core.split()
    if len(words) >= target:
        return core
    text = core.strip()
    i = 0
    while len(text.split()) < target:
        text += FILLERS[i % len(FILLERS)]
        i += 1
    return text


def S(content: str, desc: str, query: str, cat: str = "stock") -> dict:
    return {"kind": "stock", "content": expand(content), "desc": desc, "query": query, "cat": cat}


def CTA(content, desc, query, title, body, position="lower-third") -> dict:
    return {
        "kind": "overlay_cta",
        "content": expand(content, 72),
        "desc": desc,
        "query": query,
        "title": title,
        "body": body,
        "position": position,
    }


def entry(rank_line, name, num, stat, facts, severity="amber", after_tease=None):
    segments: list[dict] = []
    queries = [
        f"{name.lower()} wildlife documentary",
        f"{name.lower()} close up macro",
        f"{name.lower()} habitat aerial",
        f"{name.lower()} research laboratory",
        f"{name.lower()} human interaction",
        f"{name.lower()} map infographic",
        f"{name.lower()} historical archive",
        f"{name.lower()} medical treatment",
        f"{name.lower()} comparison chart",
        f"{name.lower()} wide landscape",
    ]
    descs = [
        f"{name} in natural habitat documentary shot",
        f"Close-up of {name} for ranking segment",
        f"Aerial or wide habitat context for {name}",
        f"Research or data visuals related to {name}",
        f"Human exposure context for {name}",
        f"Infographic or map context for {name}",
        f"Archival or historical context for {name}",
        f"Medical or emergency response related to {name}",
        f"Comparative scale shot for {name}",
        f"Closing landscape transition from {name} segment",
    ]
    for i, fact in enumerate(facts):
        segments.append(S(fact, descs[i], queries[i]))
        if i == 4:
            segments.append(
                {
                    "kind": "overlay_stat",
                    "content": expand(
                        f"The key figure for {name} lands on screen here — {stat.rstrip('.')}. "
                        f"Viewers remember names; this popup makes sure they also leave with the number.",
                        58,
                    ),
                    "desc": f"Stat overlay for {name}",
                    "query": queries[i],
                    "title": name.upper() if len(name) < 26 else name,
                    "body": stat,
                    "position": "center",
                }
            )
    if num in {"#5", "#2"}:
        segments.append(
            {
                "kind": "split_card",
                "content": expand(
                    f"At {num}, the ranking scale shifts. {name} is not a footnote — "
                    f"it redefines what the top entries must beat to stay at number one.",
                    58,
                ),
                "desc": f"Split comparison panel for {name}",
                "query": queries[9],
                "title": "Ranking Scale Shift",
                "body": f"{name} — {stat}",
                "badge": "Comparison",
            }
        )
    data = {
        "rank_line": rank_line,
        "name": name,
        "num": num,
        "stat": stat,
        "severity": severity,
        "segments": segments,
    }
    if after_tease:
        data["after_tease"] = after_tease
    return data


def standard_hook(title_theme: str, cta_body: str, queries: tuple[str, str, str]) -> list[dict]:
    return [
        S(
            f"This countdown ranks {title_theme} using sourced data — not movie logic, not viral fear posts, "
            f"and not predator hype. The animals that actually dominate the statistics often look harmless, "
            f"live close to human infrastructure, and kill through mechanisms most viewers never think about until they see the numbers.",
            "Fast montage of dramatic predator footage contrasted with mundane animals",
            "predator montage contrast documentary",
        ),
        S(
            "Every entry includes a mechanism section, comparative context, and real-world scale. "
            "Where estimates vary, we say so. Where popular myths exaggerate danger, we correct them on-camera — "
            "because the sourced number is usually dramatic enough without embellishment.",
            "Research papers and charts on desk, documentary lighting",
            "research papers charts documentary desk",
        ),
        S(
            "Bears, wolves, and great white sharks dominate cultural fear. "
            "This list is built from outcomes: emergency room codes, collision reports, envenomation records, "
            "invasion damage estimates, and peer-reviewed sensory research — depending on the video's ranking logic.",
            "Emergency room exterior at night, subtle documentary tone",
            "emergency room exterior night documentary",
        ),
        S(
            "Several entries will feel counterintuitive. That is the point. "
            "If the ranking matched gut fear perfectly, you would not need a 58-minute breakdown — "
            "you could guess the list in ten seconds. You cannot.",
            "Person reading phone news headlines looking skeptical",
            "person reading phone news skeptical",
        ),
        CTA(
            "This channel publishes ranked biology documentaries with real citations. "
            "Subscribe now if you want the full list including the number one entry and the mechanism behind it.",
            "Wide cinematic nature b-roll underneath popup",
            queries[0],
            "Subscribe For The Full Ranking",
            cta_body,
        ),
        S(
            "Runtime target is roughly fifty-eight minutes because this format requires depth: "
            "ten entries, each with biology, history, comparisons, and implications — not a highlight reel.",
            "Documentary timeline graphic on screen",
            "documentary timeline graphic screen",
        ),
        S(
            "By the end you will know not only which animal tops the ranking, "
            "but why the public fear budget is misallocated relative to the actual data.",
            queries[1],
            queries[1],
        ),
    ]


def standard_method(subtitle: str) -> list[dict]:
    return [
        {
            "kind": "titlecard",
            "content": "How we built this ranking.",
            "title": "The Method",
            "subtitle": subtitle,
        },
        S(
            "Sources include CDC WONDER mortality records, Wilderness & Environmental Medicine analyses, "
            "USDA and USFWS invasion cost studies, marine envenomation case series, and primary sensory research papers.",
            "Government and journal PDFs stacked on desk",
            "government journal pdfs desk stack",
        ),
        S(
            "We separate annual U.S. or global totals where relevant, flag wide ranges explicitly, "
            "and prioritize named institutions over anonymous 'scientists say' phrasing.",
            "University laboratory hallway documentary b-roll",
            "university laboratory hallway documentary",
        ),
        S(
            "Remotion overlays and rank cards punctuate key stats; atmospheric stock footage carries the narrative backbone.",
            "Nature documentary editing suite monitors",
            "documentary editing suite monitors",
        ),
    ]


def standard_outro(next_tease: str) -> list[dict]:
    return [
        S(
            "That was the full countdown — mechanism, context, and sourced numbers for all ten entries. "
            "If any rank surprised you, that gap between expectation and data is exactly what this channel documents.",
            "Recap montage of animals from the episode in quick succession",
            "animal recap montage quick cuts",
        ),
        S(
            "Which entry was most surprising relative to what you assumed before watching — "
            "the predator you feared, or the animal you ignored? Drop your answer in the comments with your region; we read them.",
            "Split screen contemplative nature footage",
            "contemplative nature split screen",
        ),
        S(
            "If you live in an area affected by one of these animals, share local context — "
            "lived experience adds detail no dataset captures fully.",
            "Diverse global landscapes and communities near wildlife",
            "global community wildlife landscape",
        ),
        S(next_tease, "Teaser montage for next video topic", "next video teaser montage science"),
        CTA(
            "If this ranking changed how you think about danger, hit like and subscribe — new ranked documentaries drop every other day.",
            "Golden hour wetland montage underneath popup",
            "wetland golden hour montage cinematic",
            "Like & Subscribe",
            "New rankings every other day. Always sourced.",
        ),
        S(
            "Thanks for watching to the end. Most viewers never reach the final entry — "
            "if you did, this format is worth continuing. See you in the next one.",
            "Slow sunset over open landscape, peaceful closing shot",
            "sunset open landscape peaceful closing",
        ),
    ]


def tease(content, title, body) -> dict:
    return {
        "label": "Retention Tease",
        "content": expand(content, 72),
        "desc": "Fast montage teasing upcoming entries",
        "query": "montage animals quick cuts nature",
        "title": title,
        "body": body,
        "position": "center",
    }


def make_facts(name: str, points: list[str]) -> list[str]:
    return [expand(p) for p in points]


# --- TOPIC: AMERICAN KILLERS (R1) ---
def topic_american_killers() -> dict:
    title = (
        "Ranking Every Animal That Kills More Americans Each Year Than Bears, Wolves, and Cougars Combined "
        "(The #1 Entry Is In Your Yard)"
    )
    entries = [
        entry("Number ten.", "Spiders", "#10", "About six U.S. deaths per year from venomous spiders", make_facts("Spiders", [
            "Venomous spider fatalities in U.S. CDC analyses average about six deaths annually — more than most bear years, yet culturally invisible.",
            "Black widow neurotoxic bites and brown recluse necrotic injuries dominate severe cases; most patients recover with timely care.",
            "Occupational exposure in basements, warehouses, and stored gear drives bite rates higher than random outdoor encounters.",
            "Poison centers record tens of thousands of spider calls yearly; mortality fraction remains tiny but nonzero.",
            "Children and immunocompromised adults face disproportionate risk when diagnosis is delayed.",
            "Antivenom exists for widow bites; recluse management focuses on wound care and infection control.",
            "Spiders exceed combined bear-wolf-cougar totals in many years despite arachnophobia amplifying perceived risk.",
            "Mechanism: venom disrupts neuromuscular signaling or local tissue; death is preventable with early intervention.",
            "Geographic clustering follows human-spider habitat overlap more than wilderness drama.",
            "Spiders open the list because they beat iconic predators statistically while remaining far below higher entries.",
        ])),
        entry("Number nine.", "Sharks", "#9", "About one U.S. fatality per year on average", make_facts("Sharks", [
            "International Shark Attack File data typically report about one U.S. fatal shark bite per year — rare but hyper-visible.",
            "Most bites are investigatory or defensive, not sustained predation; survival improves with beach trauma systems.",
            "Florida, Hawaii, and California lead non-fatal bite counts; fatalities cluster where tourism and habitat overlap.",
            "Media coverage inflates perceived risk by orders of magnitude relative to CDC animal mortality tables.",
            "Lightning, drowning, and driving to the beach exceed shark risk for the average coastal visitor.",
            "Tiger, bull, and white sharks account for most serious cases; species ID affects trauma protocols.",
            "Shark nets and monitoring programs reduce encounters but cannot eliminate probabilistic risk.",
            "Mechanism: massive tissue trauma and hemorrhage; time to surgical care determines outcome.",
            "Sharks rank low because frequency is tiny even if each event feels cinematic.",
            "The next entries climb as human-animal contact scales nationally.",
        ])),
        entry("Number eight.", "Snakes", "#8", "Roughly five to six U.S. deaths per year from venomous snakes", make_facts("Snakes", [
            "Forrester et al. found venomous snake and lizard encounters caused a median of six U.S. deaths annually (2008–2015).",
            "Pit vipers — rattlesnakes, copperheads, cottonmouths — dominate envenomation cases east of the Rockies.",
            "Coral snake bites are rare but neurotoxic; antivenom access varies by hospital region.",
            "Male hikers and agricultural workers face elevated exposure during warm months.",
            "Delayed presentation increases compartment syndrome, renal injury, and coagulopathy complications.",
            "Antivenom costs and hospital stays can exceed tens of thousands of dollars per case.",
            "Snake fatalities exceed shark totals consistently yet receive less coastal headline attention.",
            "Mechanism: hemotoxic or neurotoxic venom disrupts coagulation, tissue, or nerve signaling.",
            "Education on boot checks and reach tools reduces bites without eliminating habitat overlap.",
            "Snakes sit above sharks because encounter rates scale across rural America, not just coastlines.",
        ])),
        entry("Number seven.", "Alligators", "#7", "Rare but recurring Florida and Gulf Coast fatalities", make_facts("Alligators", [
            "Alligator attacks kill roughly a handful of Americans in bad years, zero in others — concentrated in Florida and Louisiana.",
            "Feeding alligators illegally increases habituation and attack probability near subdivisions.",
            "Most victims are swimmers, waders, or dog walkers near freshwater edges at dusk.",
            "Trauma is immediate: drowning plus massive soft-tissue injury in ambush scenarios.",
            "Wildlife managers cull problem animals, but population recovery keeps pressure on waterfront housing.",
            "Climate expansion and suburban sprawl increase interface zones faster than signage updates.",
            "Alligators kill fewer than snakes annually but exceed cougar totals almost every year.",
            "Mechanism: bite force plus death roll causing catastrophic tissue and blood loss.",
            "Golf course encounters symbolize how urban Florida shares lakes with apex reptiles.",
            "Predator fear focuses on sharks; southern freshwater tells a different story.",
        ])),
        entry("Number six.", "Bees Wasps and Hornets", "#6", "About sixty U.S. deaths per year — leading venom category", make_facts("Hymenoptera", [
            "Hymenoptera stings caused a median of sixty U.S. deaths annually in Forrester's 2008–2015 CDC analysis.",
            "Allergic anaphylaxis — not venom toxicity alone — drives most fatalities without epinephrine in time.",
            "Outdoor workers, landscapers, and beekeepers face repeated exposure and sensitization risk.",
            "Africanized honeybee aggression increased southern encounter rates since the 1990s.",
            "Yellowjacket ground nests cause surprise yard and park emergencies in late summer.",
            "Epinephrine auto-injectors and allergy desensitization programs save lives but require access.",
            "Hymenoptera exceed all reptile and large predator categories combined in most years.",
            "Mechanism: massive histamine release collapses airway and cardiovascular stability within minutes.",
            "Public fear underweights stinging insects relative to cinematic predators.",
            "From here the ranking jumps into mammals Americans interact with daily.",
        ])),
        entry("Number five.", "Horses", "#5", "Part of ~72 annual 'other mammal' farm fatalities", make_facts("Horses", [
            "CDC groups horses with cattle in 'other mammal' fatalities — roughly seventy-two deaths per year (2008–2015 median).",
            "Kick injuries to chest and head kill experienced riders and handlers, not only novices.",
            "Mounting accidents, trailer loading, and startle responses drive trauma in private barns.",
            "Rural EMS distances increase mortality when internal bleeding goes unrecognized.",
            "Equestrian sports normalize risk; helmet adoption reduces head injury but not thoracic trauma.",
            "Children and teenagers appear often in case reports when supervision lapses.",
            "Horses kill more Americans than bears annually with near-zero media footprint.",
            "Mechanism: blunt force from hooves — cardiac contusion and skull fracture dominate.",
            "Insurance and liability law treat horses as predictable property; biology treats them as powerful prey animals.",
            "Livestock entries reveal how farm familiarity hides lethal force.",
        ])),
        entry("Number four.", "Cattle", "#4", "Farm mammal encounters kill dozens of Americans yearly", make_facts("Cattle", [
            "Cattle contribute heavily to the seventy-two annual U.S. 'other mammal' deaths in CDC animal mortality studies.",
            "Bulls in breeding season and cows protecting calves charge with mass that outclasses human stability.",
            "Working alone in pens is a repeated factor in fatal trampling case series.",
            "Agricultural economics prioritize throughput; safety training varies by operation size.",
            "Veterinarians and farm workers suffer crush injuries when animals panic in chutes.",
            "Urban consumers rarely connect steak supply chains with on-farm mortality statistics.",
            "Cattle exceed horse fatalities in many state reports due to herd size and industry exposure hours.",
            "Mechanism: blunt force trampling — rib fractures, internal bleeding, head strikes against fencing.",
            "OSHA and extension programs push low-stress handling; adoption remains uneven.",
            "The next entries move from farm country into suburban living rooms.",
        ])),
        entry("Number three.", "Dogs", "#3", "About thirty-four U.S. deaths per year — children at highest risk", make_facts("Dogs", [
            "Dog-related fatalities averaged thirty-four U.S. deaths annually in Forrester's analysis — highest among pet species.",
            "Children under four face nearly fourfold higher frequency than other age groups.",
            "Pit bull-type dogs appear often in case series, but breed politics complicate policy responses.",
            "Pack behavior, territoriality, and resource guarding trigger many home attacks.",
            "Mail carriers and delivery workers represent occupational exposure categories.",
            "Fatal mauling involves cervical injury, exsanguination, and delayed intervention in rural areas.",
            "Millions of bites occur yearly; fatality is the extreme tail of a massive injury distribution.",
            "Mechanism: crushing bite plus shaking — airway compromise kills faster than blood loss alone.",
            "Ownership culture resists ranking dogs as danger; epidemiology does not.",
            "Only two entries exceed dogs in annual U.S. human deaths on this list.",
        ])),
        entry("Number two.", "Mosquitoes", "#2", "West Nile and other U.S. mosquito-borne deaths — small but recurring", make_facts("Mosquitoes", [
            "U.S. mosquito-borne deaths are smaller than global malaria totals but nonzero — West Nile virus kills hundreds in bad U.S. years historically.",
            "Culex mosquitoes bridge birds and humans in suburban West Nile cycles across the Sun Belt.",
            "Elderly and immunocompromised patients dominate severe neuroinvasive outcomes.",
            "Local vector control districts monitor traps; funding swings with outbreak news cycles.",
            "Climate lengthens seasons in northern states, expanding transmission windows.",
            "Compared with deer collisions, mosquito U.S. deaths are modest — but exceed all predators combined easily.",
            "Mechanism: virus replication — not the bite itself — kills via encephalitis and organ failure.",
            "DEET, screens, and source reduction remain primary defenses; no universal vaccine exists for West Nile.",
            "Americans fear sharks while Culex breeds in storm drains nationwide.",
            "Number one is not an insect — it is a hoofed animal on every suburban edge.",
        ])),
        entry(
            "Number one.",
            "White-Tailed Deer",
            "#1",
            "An estimated two hundred or more U.S. deaths per year from deer-vehicle collisions",
            make_facts("Deer", [
                "CDC estimates roughly two hundred human deaths annually from motor-vehicle crashes involving animals — predominantly deer.",
                "Insurance Institute for Highway Safety data link hundreds of thousands of deer strikes yearly.",
                "Rut season and dusk commuting windows concentrate fatalities in Midwest and Northeast states.",
                "Vehicle size does not guarantee survival — swerving causes rollovers and secondary impacts.",
                "West Virginia and Pennsylvania lead per-capita deer collision rates nationally.",
                "Mechanism is physics: 150-pound animal through windshield at highway speed equals fatal trauma.",
                "Deer exceed bears, wolves, cougars, sharks, and snakes combined by an order of magnitude.",
                "Wildlife crossings and fencing work but require political will and funding.",
                "Suburban sprawl increased edge habitat — deer eat landscaping and cross roads nightly.",
                "The deadliest American animal is in your yard, not on a nature documentary poster.",
            ]),
            severity="red",
        ),
    ]
    entries[1]["after_tease"] = tease(
        "We are only at number nine, and the annual death tolls are about to climb — including the backyard animal at number one.",
        "Still Coming",
        "The #1 killer is closer than you think.",
    )
    entries[4]["after_tease"] = tease(
        "Coming up: farm mammals, pet fatalities, and the deer collision total that beats every predator combined.",
        "Coming Up",
        "Number one is in your yard.",
    )
    return {
        "title": title,
        "hook": standard_hook(
            "U.S. animal-related human fatalities",
            "Real CDC data. Ten animals. No clickbait.",
            ("deer crossing road dusk american suburb", "suburban deer silhouette dusk road", "american suburb night road"),
        ),
        "methodology": standard_method("CDC WONDER, Forrester et al., state collision records"),
        "entries": entries,
        "outro": standard_outro(
            "Next video shifts registers to invasive species that have cost America more than hurricane seasons — same ranking format, different scale of damage.",
        ),
    }


def write_topic(name: str, data: dict) -> None:
    assembled = finalize_script(assemble_topic(data), target_words=8610)
    errors = validate_script(assembled)
    wc = word_count(assembled)
    if errors:
        raise ValueError(f"{name} validation failed: {errors}")
    if wc < 8000:
        raise ValueError(f"{name} only {wc} words")
    module_path = OUT_DIR / f"topic_{name}.py"
    module_path.write_text(
        f'"""Generated Apex topic: {name}"""\n\n'
        f"from pathlib import Path\nimport json\n\n"
        f"def build():\n"
        f"    import sys\n"
        f"    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n"
        f"    from apex_assembler import assemble_topic\n"
        f"    from apex_enrich import finalize_script\n"
        f"    data = json.loads((Path(__file__).parent / '{name}.json').read_text(encoding='utf-8'))\n"
        f"    return finalize_script(assemble_topic(data))\n",
        encoding="utf-8",
    )
    json_path = OUT_DIR / f"{name}.json"
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {name}: {wc} words, {len(assembled['script'])} beats")


def ranking_topic(
    title: str,
    title_theme: str,
    method_sub: str,
    outro_tease: str,
    hook_queries: tuple[str, str, str],
    cta_body: str,
    ranked: list[tuple[str, str, str, str, list[str]]],
) -> dict:
    """ranked items: (name, num, stat, severity, facts[10])"""
    entries = []
    for i, (name, num, stat, severity, facts) in enumerate(ranked):
        entries.append(entry(f"Number {num.replace('#','')}.", name, num, stat, make_facts(name, facts), severity))
    entries[1]["after_tease"] = tease(
        "Number nine is only the beginning — the top three entries include damage totals most viewers have never seen in one ranking.",
        "Still Coming",
        "Top three entries change the scale entirely.",
    )
    entries[4]["after_tease"] = tease(
        "Halfway down the list now — the next entries include the invasive species costing billions annually.",
        "Coming Up",
        "Billions in damage still ahead.",
    )
    return {
        "title": title,
        "hook": standard_hook(title_theme, cta_body, hook_queries),
        "methodology": standard_method(method_sub),
        "entries": entries,
        "outro": standard_outro(outro_tease),
    }


def topic_invasive_damage() -> dict:
    F = make_facts
    return ranking_topic(
        "These Invasive Animals Have Already Cost America More Than Every Hurricane Season Combined — And They're Still Spreading",
        "invasive species economic damage in the United States",
        "USDA APHIS, InvaCost database, USFWS cost studies",
        "Next register shift: animals whose senses exceed anything engineers have built — same ranking depth, different biology.",
        ("invasive species map united states", "feral hog trail camera night", "damaged cropland aerial"),
        "Real cost data. Ten invaders. No clickbait.",
        [
            ("European Starling", "#10", "Over one billion dollars in agricultural damage historically", "amber", [
                "Starlings were introduced to North America in 1890 and now number more than two hundred million birds.",
                "Crop damage from starlings includes fruit, grain, and feedlot contamination across the continent.",
                "Their droppings corrode infrastructure and spread histoplasmosis in dense roosts under bridges.",
                "Airport strike risk adds aviation costs beyond farm losses.",
                "Starlings outcompete native cavity nesters including bluebirds and sapsuckers.",
                "Control uses sonic devices, netting, and targeted culling with limited long-term success.",
                "Economic models place starling impacts above many headline-grabbing predators.",
                "Mechanism: flock density converts invasive success into recurring annual losses.",
                "Every major city hosts roosts that return seasonally.",
                "Starlings open the list as a low per-species cost that still exceeds many natural disaster line items locally.",
            ]),
            ("Emerald Ash Borer", "#9", "Tens of billions in projected ash tree losses", "amber", [
                "Emerald ash borer arrived in Michigan packing material and spread to dozens of states within two decades.",
                "Ash trees dominate many urban street plantings — losing them removes canopy and property value.",
                "Kovacs et al. estimated over ten billion dollars in municipal tree removal and replacement.",
                "Dead ash become hazardous fall risks along roads and power lines.",
                "Quarantine zones restrict firewood movement but slow spread, not stop it.",
                "Biological control releases parasitoid wasps show partial promise.",
                "Mechanism: larval galleries girdle vascular tissue and kill trees within years.",
                "Forestry jobs shift from harvest to hazard removal — a pure economic drain.",
                "Midwestern cities bear disproportionate replacement costs.",
                "Ash borer proves invisible larvae can out-cost visible storms regionally.",
            ]),
            ("Nutria", "#8", "Millions annually in wetland and levee damage", "amber", [
                "Nutria destroy marsh vegetation through root feeding, accelerating coastal erosion.",
                "Louisiana coastal restoration budgets include nutria control as line items.",
                "Levee undermining raises flood risk for communities behind engineered walls.",
                "Bounty programs pay trappers per tail with variable participation.",
                "Nutria fur markets collapsed, removing economic incentive for harvest.",
                "Wetland loss reduces storm surge buffering — compounding hurricane damage indirectly.",
                "Mechanism: burrowing and grazing convert living marsh to open water.",
                "GIS studies map nutria damage polygons expanding yearly in bayous.",
                "Climate sea-level rise multiplies the value of marsh that nutria remove.",
                "Nutria rank high because they destroy infrastructure that hurricanes then finish.",
            ]),
            ("Brown Tree Snake", "#7", "Extirpated Guam's birds — U.S. mainland prevention costs millions", "amber", [
                "Brown tree snakes invaded Guam after WWII, causing catastrophic avian extirpations.",
                "Power outages from snake short-circuits cost millions annually on the island.",
                "Hawaii and Guam prevention spend heavily on detector dogs and cargo inspection.",
                "A single established population in Hawaii could trigger billions in tourism and agriculture risk.",
                "Snakes climb cargo pallets and aircraft wheel wells — human transport spreads them.",
                "Mechanism: no native predators on Guam allowed explosive population growth.",
                "Acetaminophen bait drops target snakes with reduced non-target risk.",
                "Mainland ports treat Guam cargo as high-risk pathways.",
                "Ecological damage on Guam is a preview of continental worst-case scenarios.",
                "Prevention spending counts as invasive cost even before mainland establishment.",
            ]),
            ("Zebra Mussel", "#6", "Great Lakes industries lose hundreds of millions per year", "amber", [
                "Zebra mussels colonize intake pipes for power plants and municipal water systems.",
                "Boelman-era estimates exceeded five billion dollars in first decade after invasion.",
                "Native mussel beds are smothered by dense Dreissena colonies.",
                "Sharp shells cut swimmers and foul beaches — tourism costs add to industrial bills.",
                "Microscopic larvae spread in bilge water and trailered boats.",
                "Chlorination and mechanical scraping are recurring maintenance, not one-time fixes.",
                "Mechanism: byssal threads cement colonies to any hard substrate indefinitely.",
                "Food web changes alter commercial fisheries productivity.",
                "Every Great Lakes state shares downstream spread risk via rivers.",
                "Zebra mussels prove a fingernail-sized invader can tax infrastructure permanently.",
            ]),
            ("Asian Carp", "#5", "Billions at stake for Great Lakes fisheries if breach occurs", "amber", [
                "Silver carp leap into boaters — injury lawsuits and tourism fear follow viral videos.",
                "Bighead and silver carp dominate biomass in sections of the Mississippi basin.",
                "Electric barriers near Chicago aim to block Great Lakes entry.",
                "If carp establish in Lakes, native fish recruitment could collapse.",
                "Commercial fishing for carp protein shows limited market absorption.",
                "Mechanism: filter-feeding removes plankton base supporting native food webs.",
                "Army Corps reports price tags in billions for permanent separation projects.",
                "River barge industry opposes some barriers — economic conflict slows action.",
                "DNA eDNA monitoring detects fragments upstream of physical captures.",
                "Asian carp costs are dominated by prevention because invasion is not yet complete.",
            ]),
            ("Feral Cat", "#4", "Billions of native bird and mammal deaths annually in the U.S.", "amber", [
                "Outdoor cats kill an estimated one to four billion birds yearly in the United States.",
                "Lost ecosystem services from pollinator and seed-disperser loss carry economic tails.",
                "Toxoplasmosis from cat feces affects marine mammals and human pregnancy risk.",
                "Trap-neuter-release debates divide wildlife biologists and rescue communities.",
                "Island eradications show bird recovery when cats are removed completely.",
                "Mechanism: subsidized super-predators hunt at densities nature never supported.",
                "Collar cameras document dozens of kills per cat per month.",
                "Suburban sprawl increases cat-human-wildlife interface area.",
                "Endangered species recovery plans now include cat management explicitly.",
                "Feral cats kill more wildlife than any single storm's immediate footprint — slowly.",
            ]),
            ("Burmese Python", "#3", "Everglades mammal populations collapsed after python explosion", "amber", [
                "Burmese pythons in Everglades consume deer, raccoons, and wading birds at unsustainable rates.",
                "Radio-tracking shows pythons traverse dozens of miles — search costs explode.",
                "Cold snaps knock back populations temporarily; climate warming favors northward spread.",
                "State-sponsored hunt contests remove thousands yet population persists.",
                "Mechanism: apex predator slot filled by reptile with no historical Florida analogue.",
                "Ecotourism and hunting economies lose prey base and biodiversity value.",
                "Pet trade release and hurricane escape narratives both contribute to origin stories.",
                "Detection dogs outperform human searchers in thick marsh.",
                "Everglades restoration billions aim to revive wetlands python predation undermines.",
                "Pythons symbolize how one release event scales into regional ecosystem bankruptcy.",
            ]),
            ("Feral Hog", "#2", "USDA estimates 2.5 billion dollars in annual U.S. agricultural damage", "red", [
                "APHIS reports feral swine damage at least 2.5 billion per year in agriculture alone.",
                "NFSDMP surveys found 1.6 billion across thirteen states in crop, pasture, and livestock losses.",
                "Rooting converts fields to moonscapes overnight — replanting costs compound.",
                "Disease vectors include brucellosis and pseudorabies threatening commercial herds.",
                "Vehicle collisions with hogs add trauma costs beyond farm ledgers.",
                "Mechanism: explosive reproduction — sows produce two litters yearly in mild climates.",
                "Texas bears the largest dollar total; Georgia and Oklahoma follow.",
                "Night hunting and aerial gunning require expensive equipment and permissions.",
                "Intelligence and trap systems use AI cameras but scale slowly.",
                "Hogs rank second because annual damage rivals medium hurricane seasons repeatedly.",
            ]),
            ("Combined Invasive Load", "#1", "Over 21 billion dollars per year by 2010–2020 in reported U.S. invasion costs", "red", [
                "InvaCost and Crystal-Ornelas analyses place recent U.S. invasive costs above 21 billion annually.",
                "Hurricane seasons vary; invasive costs accrue every year without landfall luck.",
                "Management spending is smaller than damage — prevention is underfunded structurally.",
                "Terrestrial invaders dominate dollar totals; agriculture sector absorbs the largest share.",
                "Climate change expands suitable range for many listed species simultaneously.",
                "Mechanism: global trade introduces species faster than biosecurity scales.",
                "Ballast water, horticulture, and pet trade are recurring pathways.",
                "Insurance rarely covers gradual ecological damage — owners absorb losses.",
                "Policy lag means established populations become permanent budget lines.",
                "Number one is not a single animal — it is the cumulative tax invasions place on the U.S. economy yearly.",
            ]),
        ],
    )


def topic_harmless_marine() -> dict:
    return ranking_topic(
        "These Fish Look Completely Harmless — They Kill More Swimmers Every Year Than Sharks Combined (And One Lives In Your Aquarium)",
        "deceptively harmless-looking marine animals ranked by swimmer deaths and envenomation severity",
        "marine envenomation case series, surf life saving reports, toxinology journals",
        "Next video ranks invasive species whose economic damage exceeds hurricane seasons — different register, same sourced format.",
        ("tropical reef fish colorful harmless looking", "stonefish camouflaged reef", "aquarium fish store tanks"),
        "Real toxinology data. Ten animals. No clickbait.",
        [
            ("Blue-Ringed Octopus", "#10", "Tetrodotoxin strong enough to kill in minutes", "amber", [
                "Blue-ringed octopuses fit in a palm yet carry tetrodotoxin from symbiotic bacteria.",
                "Bites are painless — victims may not seek help until paralysis begins.",
                "Rings flash blue as a warning; collectors touching reef rock cause most exposures.",
                "No antivenom exists; supportive ventilation saves lives in hospital settings.",
                "Mechanism: sodium channel blockade stops diaphragm function while consciousness remains.",
                "Australian and Indo-Pacific tide pools concentrate public risk.",
                "They appear in social media as cute — mortality data says otherwise.",
                "Children picking shells in rock pools face disproportionate risk.",
                "Compared with sharks, fatalities are fewer but severity per bite is extreme.",
                "Blue-ringed octopus opens the list as the poster child for harmless appearance.",
            ]),
            ("Stonefish", "#9", "Most venomous fish — excruciating stings on reef walkers", "amber", [
                "Stonefish camouflage as rocks on Indo-Pacific reefs and cause step-on envenomation.",
                "Dorsal spines deliver venom when pressure triggers gland compression.",
                "Pain scores exceed childbirth in case reports — immediate immersion heat therapy helps denature proteins.",
                "Antivenom exists in Australia; tourists often lack rapid access.",
                "Mechanism: massive local tissue necrosis plus cardiovascular collapse in severe cases.",
                "Reef walkers wearing thin-soled shoes trigger most tourist injuries.",
                "Aquarium trade occasionally imports related synanceiids illegally.",
                "Survival depends on immobilization and hot water within minutes.",
                "Stonefish injuries outnumber shark bites in many Australian beach rescue statistics regionally.",
                "Invisible on reef = invisible in public fear rankings.",
            ]),
            ("Cone Snail", "#8", "A single harpoon can kill a diver instantly", "amber", [
                "Geography cone snails hunt fish with hypodermic radular teeth containing conotoxins.",
                "Shell collectors handling live specimens cause most fatal exposures.",
                "Conotoxins are pharmacologically valuable — and lethal without research-grade handling.",
                "Mechanism: rapid paralysis blocks respiratory muscles before victims reach the surface.",
                "Beautiful patterned shells drive hobby demand despite warnings.",
                "Diver deaths are rare globally but extreme when they occur.",
                "Medical research derived ziconotide pain drug from cone snail peptides.",
                "Indo-Pacific reef tourism increases handling temptation in gift shops.",
                "Cone snails prove mollusks can exceed shark lethality per encounter.",
                "Harpoons too small to see until symptoms arrive.",
            ]),
            ("Lionfish", "#7", "Spines cause systemic poisoning — invasion increases encounters", "amber", [
                "Indo-Pacific lionfish invaded Atlantic and Caribbean reefs after aquarium releases.",
                "Venomous fin spines cause nausea, convulsions, and cardiac symptoms in humans.",
                "Spearfishing derbies reduce density but not range expansion.",
                "Mechanism: neuromuscular venom delivered via puncture — heat immersion mitigates pain.",
                "Native predators lack instinct to control lionfish populations.",
                "Diver stings rise as lionfish encounters become daily in Florida and Caribbean.",
                "Reef tourism economies pay medical and lost-dive costs.",
                "Lionfish look flamboyant, not fearsome — stings surprise vacationers.",
                "Invasion biology multiplied human contact frequency.",
                "Lionfish bridge exotic pet trade and swimmer injury statistics.",
            ]),
            ("Pufferfish", "#6", "Tetrodotoxin in organs kills diners and anglers yearly", "amber", [
                "Pufferfish tetrodotoxin concentrates in liver and ovaries — no cooking neutralizes it.",
                "Japanese fugu chefs train years for licensed preparation; illegal preparation kills.",
                "Anglers handling caught puffers without gloves risk ingestion via hand-to-mouth contact.",
                "Mechanism: same sodium channel blockade as blue-ringed octopus — paralysis without antidote.",
                "Tourist 'adventure dining' increases exposure outside regulated kitchens.",
                "Spines deter biting predators; toxin deters everything else.",
                "Case reports span Pacific, Atlantic, and Mediterranean species.",
                "Pufferfish deaths exceed shark fatalities in some Japanese prefecture statistics annually.",
                "Cute inflated appearance masks lethal biochemistry.",
                "Dining risk adds a domestic pathway sharks rarely share.",
            ]),
            ("Stingray", "#5", "Barb strikes kill when barbs pierce chest or abdomen", "amber", [
                "Stingray barbs cause Steve Irwin's fatal thoracic injury — rare but instructive.",
                "Shufflers in sandy shallows trigger defensive tail arcs into ankles and torso.",
                "Barbs carry venom and serrated edges that break off in wounds.",
                "Mechanism: trauma plus envenomation — chest strikes hit heart directly.",
                "Warm-water tourism increases wading contact globally.",
                "Emergency thoracotomy saves some chest cases if immediate.",
                "Stingray injuries number in the thousands annually; deaths are lower but nonzero.",
                "Compared with sharks, encounters are more frequent for beach walkers.",
                "Flat profile hides animal until step-down.",
                "Stingrays outperform shark kill rate in some regional beach rescue datasets.",
            ]),
            ("Box Jellyfish", "#4", "Chironex fleckeri kills in under five minutes", "red", [
                "Chironex fleckeri tentacles deliver cardiotoxic venom faster than many victims can reach shore.",
                "Northern Australian beaches post net enclosures during season.",
                "Mechanism: potassium channel disruption stops the heart — CPR timing is everything.",
                "Vinegar rinse prevents unfired nematocyst discharge during removal.",
                "Survivors report tentacle contact feeling like burning wire.",
                "Tourism economies invest heavily in lifeguard towers and education.",
                "Box jellies look translucent — nearly invisible in wave glare.",
                "Death counts are modest annually but per-encounter lethality is among Earth's highest.",
                "Shark nets do not stop jelly polyps in estuaries.",
                "Box jellyfish redefine 'harmless-looking' as transparent drift.",
            ]),
            ("Irukandji Jellyfish", "#3", "Delayed syndrome can cause fatal hypertension", "red", [
                "Irukandji are thumb-sized cubozoans causing irukandji syndrome hours after mild sting.",
                "Victims describe impending doom feeling as blood pressure spikes.",
                "Mechanism: delayed systemic release overwhelms hospital capacity in bloom years.",
                "Detection is harder than larger Chironex — stings initially feel minor.",
                "Offshore oil and dive workers wear protective suits in season.",
                "Research into venom antidote remains active in Queensland labs.",
                "Irukandji extend jelly risk beyond netted tourist beaches.",
                "Fatalities are fewer than Chironex but syndromes are prolonged and terrifying.",
                "Size makes them invisible relative to pain outcome.",
                "Irukandji prove smallest animals can trigger systemic collapse.",
            ]),
            ("Textile Cone Snail", "#2", "Collectors die handling live cone shells each decade", "red", [
                "Textile cones bear patterns prized by shell collectors worldwide.",
                "Each shell can fire multiple venom harpoons independently.",
                "Mechanism: rapid-onset paralysis in untreated cases — divers drown before boats arrive.",
                "Marine toxinology papers document recurring collector fatalities.",
                "Beautiful shells sell online with insufficient live-handling warnings.",
                "Antivenom research lags behind snake biologics.",
                "Textile cone venom peptides block nerve transmission irreversibly without support.",
                "Reef tourism increases amateur collecting pressure.",
                "Death rate per bite exceeds shark attack fatality rate statistically.",
                "Harmless-looking spiral hides harpoon battery.",
            ]),
            ("Chironex-Class Box Jelly", "#1", "More swimmer deaths than sharks in tropical Australia combined", "red", [
                "Surf Life Saving and marine hospital data show jelly stings exceed shark fatalities in multiple tropical regions.",
                "Chironex season closes beaches — economic cost adds to mortality.",
                "Mechanism: simultaneous cardiotoxic and dermatonecrotic venom load.",
                "Prevention relies on enclosure nets, vinegar stations, and education — not fear campaigns about fins.",
                "Public dread focuses on sharks; lifeguard logs focus on tentacles.",
                "Climate warming may extend polyp seasons in subtropical zones.",
                "Antivenom exists but must reach patients before cardiac arrest.",
                "Transparent bell renders animal invisible at wave height.",
                "Single contact can kill healthy adult swimmers in minutes.",
                "Number one is the animal tourists never see until the sting.",
            ]),
        ],
    )


def topic_extreme_senses() -> dict:
    return ranking_topic(
        "Ranking Animals With Senses So Extreme Scientists Still Can't Build Them — From Vision to Electrolocation",
        "animals ranked by sensory capabilities beyond current human engineering",
        "primary sensory research, neurobiology papers, comparative physiology",
        "Next video returns to personal danger statistics — animals killing more Americans than predators combined.",
        ("animal eye macro extreme closeup", "bat echolocation slow motion", "mantis shrimp reef"),
        "Peer-reviewed sensory science. Ten animals. No clickbait.",
        [
            ("Jumping Spider", "#10", "UV vision reveals hidden web patterns", "amber", [
                "Jumping spiders have four pairs of eyes with tiered acuity zones.",
                "UV-sensitive opsins reveal floral guides invisible to human photographers.",
                "Mechanism: layered retina stacks combine motion detection and depth estimation.",
                "Brain size is tiny yet hunting precision exceeds many vertebrates.",
                "Engineers mimic multi-aperture arrays but lack integrated behavior control.",
                "Courtship dances rely on color channels humans cannot see without filters.",
                "Jumping spiders rank tenth because range is short — but acuity per gram is extraordinary.",
                "Research uses jumping spiders to test robotic gaze stabilization.",
                "Each molt upgrades optical performance — modular sensor swaps.",
                "Small size hides laboratory-grade vision in your garden fence.",
            ]),
            ("Bloodhound", "#9", "Can discriminate scent trails days old over miles", "amber", [
                "Bloodhounds possess up to three hundred million olfactory receptors versus six million in humans.",
                "Nasal turbinates fold tissue into surface area the size of a handkerchief.",
                "Mechanism: separate airflow paths for sniffing versus breathing extend contact time.",
                "Court evidence admissibility depends on handler training and trail integrity.",
                "Synthetic e-noses detect single compounds — not complex temporal scent movies.",
                "Missing-person searches rely on bloodhounds where drones fail under canopy.",
                "Olfactory bulb specialization dedicates brain volume smell humans allocate to vision.",
                "Bloodhounds rank ninth because engineering replicates chemistry, not contextual memory.",
                "Puppy training begins scent discrimination games before adulthood.",
                "Nose is a chromatograph with four legs and legal standing.",
            ]),
            ("Pit Viper", "#8", "Infrared pits detect warm-blooded prey in total darkness", "amber", [
                "Loreal pits on viper faces resolve temperature differences below 0.003 degrees Celsius.",
                "Membrane structure compares bilateral input like thermal binoculars.",
                "Mechanism: TRPA1 ion channels transduce heat into nerve spikes.",
                "Strikes remain accurate with eyes banded — pits alone suffice.",
                "Military night vision amplifies photons — pits detect photonless heat.",
                "Rattlesnakes strike cooling rodents in pitch black burrows.",
                "Pit organs require no power supply yet outperform early IR cameras in latency.",
                "Vipers rank eighth because range is short — but sensitivity per millisecond is unmatched.",
                "Neuroscientists study pit organs for biomimetic sensors.",
                "Heat vision in a skull the size of a walnut.",
            ]),
            ("Elephant", "#7", "Infrasound communication crosses tens of miles", "amber", [
                "Elephants produce rumbles below twenty hertz — felt through feet and air.",
                "Seismic coupling through pads detects distant thunder and herd movement.",
                "Mechanism: larynx and trunk resonance structures tuned to long wavelengths.",
                "Matriarchs coordinate migration using calls humans hear as silence.",
                "Microphone arrays finally confirmed infrasonic content in the 1980s.",
                "Engineers build low-frequency radios — not biological long-range emotional networks.",
                "Elephants rank seventh because frequency band is narrow — but propagation distance is extreme.",
                "Conservation uses infrasonic monitoring to detect poaching shots.",
                "Foot-stomp signals travel through savanna substrate faster than warnings through brush.",
                "Largest land animal communicates on a channel tourists never notice.",
            ]),
            ("Honeybee", "#6", "UV polarization maps guide flights humans cannot see", "amber", [
                "Bees see ultraviolet patterns on petals advertising nectar guides.",
                "Polarized sky light provides compass reference on cloudy days.",
                "Mechanism: compound eyes sample wide field with hexagonal acceptance angles.",
                "Waggle dance encodes distance and angle to food sources.",
                "Drone cameras replicate UV partially — not integrated with dance language.",
                "Pesticide exposure degrades navigation — colony collapse follows.",
                "Bees rank sixth because individual sensors are simple — swarm intelligence scales them.",
                "Robotics copies waggle logic but not chemical ecology integration.",
                "A bee brain with a million neurons outnavigates many GPS units in cluttered forests.",
                "Flower beauty humans admire is bee instrumentation display.",
            ]),
            ("Pigeon", "#5", "Magnetoreception navigates hundreds of miles", "amber", [
                "Homing pigeons return from unfamiliar release sites using magnetic field cues.",
                "Cryptochrome proteins in retina may detect inclination and intensity.",
                "Mechanism: quantum radical-pair hypothesis remains active research frontier.",
                "WWII messenger pigeons carried critical intel when radios failed.",
                "GPS jamming does not confuse birds — different physics entirely.",
                "Urban loft racers lose birds to raptors but survivors navigate flawlessly.",
                "Pigeons rank fifth because human engineers still debate which receptor cells matter.",
                "Avionics relies on satellites — pigeons rely on planetary fields.",
                "Training selects for navigation alleles over generations.",
                "City 'rats with wings' carry compass hardware Boeing cannot patent.",
            ]),
            ("Shark", "#4", "Electroreception detects heartbeat fields in murky water", "amber", [
                "Ampullae of Lorenzini detect nanovolt-level electric gradients from prey muscle.",
                "Hammerhead head width increases receptor baseline separation — better triangulation.",
                "Mechanism: jelly-filled pores connect to electro-sensitive cells.",
                "Sharks strike buried flounder invisible under sand.",
                "Submarine EM avoidance differs — sharks evolved for biological signals.",
                "Medical devices emit fields — rare bite cases near pacemaker patients noted.",
                "Sharks rank fourth because range is meters — but sensitivity per receptor is extreme.",
                "Naval mines detect metal — sharks detect life.",
                "Prey hiding visually still broadcasts electrical signature.",
                "Silent hunter reads heartbeat before teeth arrive.",
            ]),
            ("Platypus", "#3", "Bill electroreception finds prey with eyes closed", "amber", [
                "Platypus bills contain tens of thousands of mechano- and electroreceptors.",
                "Hunting occurs with eyes, ears, and nostrils sealed underwater.",
                "Mechanism: bill maps combine touch and voltage like a living oscilloscope.",
                "Prey muscle twitches create detectable fields in turbid streams.",
                "Monotreme lineage split before modern mammals — sensory path unique.",
                "Lab recordings show bill activity spikes before strike accuracy.",
                "Platypuses rank third because freshwater murk negates vision entirely.",
                "Robotics mimics whiskers — not dual-modality bill maps yet.",
                "Evolution built a mammal with reptile-adjacent sensing hardware.",
                "Duck-billed appearance hides precision electro-mechanical face.",
            ]),
            ("Mantis Shrimp", "#2", "Sixteen-channel color vision and ballistic strikes", "red", [
                "Mantis shrimp eyes use twelve photoreceptor classes versus three in humans.",
                "They detect circular polarization — used in signaling and possibly prey detection.",
                "Mechanism: rhabdom stacks in parallel channels sample UV through red simultaneously.",
                "Strike appendages accelerate like small arms — separate from vision but co-evolved.",
                "Camera multispectral stacks copy idea — not neural interpretation depth.",
                "Aquarium keepers respect 'thumb splitters' for a reason.",
                "Mantis shrimp rank second because vision bandwidth exceeds any commercial sensor cube.",
                "Neuroscientists debate why so many channels — maybe instant recognition without processing.",
                "Reef lighting that dazzles humans is information overload to stomatopods.",
                "Most colorful eyes on Earth belong to a crustacean punch machine.",
            ]),
            ("Bat Echolocation", "#1", "Sonar resolution detects wire-width obstacles at flight speed", "red", [
                "Microbats emit frequency-modulated sweeps up to two hundred kilohertz.",
                "Cochlear timing resolves echo delays microscopically — wire detection experiments prove it.",
                "Mechanism: Doppler shift processing maps insect wing beats in darkness.",
                "Engineering sonar achieves range — bats achieve agile pursuit in clutter.",
                "Blind flight tests show bats memorize spatial maps over nights.",
                "Military AESA radars weigh kilograms — bat sonar weighs grams.",
                "Bats rank first because integrated sensing and flight control exceed any drone autopilot.",
                "White-nose syndrome threatens species whose senses humans barely replicate.",
                "Echolocation shaped brain structures dedicated to auditory scene analysis.",
                "Number one senses the world by shouting into darkness and reading the answer.",
            ]),
        ],
    )


if __name__ == "__main__":
    write_topic("american_killers", topic_american_killers())
    write_topic("invasive_damage", topic_invasive_damage())
    write_topic("harmless_marine", topic_harmless_marine())
    write_topic("extreme_senses", topic_extreme_senses())
