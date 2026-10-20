#!/usr/bin/env python3
"""Emit one Catala module per SARA case from the grounded world models.

Each case becomes a `Case_<id>.catala_en` exposing the world model, the
case-injected statute conclusions, and the query the case tests.  Catala 1.2 has
no string type, so every atom, date and number is interned into one integer key
space (shared across all cases so the ids are stable and comparable); the
symbol table is written to .port/sara/build/symbols.json for reporting.

Predicates whose Catala section has not been ported yet emit a query marked
UNPORTED, so the differential runner can report coverage growing section by
section rather than failing wholesale.
"""
from __future__ import annotations

import json
import itertools
import re
from datetime import date
from .paths import CATALA_PROJECT

OUT = CATALA_PROJECT / "cases"

DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
VAR_RE = re.compile(r"^_VAR\d+$")
# Prolog numeric amounts are rendered as whole-dollar Catala money values.


class EventCardinalityError(ValueError):
    """A generated world lies outside the Catala port's bounded event schema."""

# events.pl unary predicates -> typed World category fields.
EVENT_KINDS = {
    "marriage_": "Marriage", "birth_": "Birth", "death_": "Death",
    "income_": "Income", "payment_": "Payment", "service_": "Service",
    "residence_": "Residence", "migration_": "Migration",
    "retirement_": "Retirement", "deduction_": "Deduction",
    "enrollment_": "Enrollment", "termination_": "Termination",
    "incarceration_": "Incarceration", "legal_separation_": "LegalSeparation",
    "joint_return_": "JointReturn", "itemize_deductions_": "ItemizeDeductions",
    "blindness_": "Blindness", "disability_": "Disability",
    "attending_classes_": "AttendingClasses",
    "medical_patient_": "MedicalPatient",
    "nonresident_alien_": "NonresidentAlien", "citizenship_": "Citizenship",
    "son_": "Son", "daughter_": "Daughter", "father_": "Father",
    "mother_": "Mother", "brother_": "Brother", "sister_": "Sister",
    "sibling_": "Sibling", "business_": "Business",
    "business_trust_": "BusinessTrust", "plan_": "Plan",
    "hospital_": "Hospital", "medical_institution_": "MedicalInstitution",
    "penal_institution_": "PenalInstitution",
    "educational_institution_": "EducationalInstitution",
    "nurses_training_school_": "NursesTrainingSchool",
    "international_organization_": "InternationalOrganization",
    "american_employer_": "AmericanEmployer",
    "unemployment_compensation_agreement_": "UnemploymentCompensationAgreement",
}

# World field for each unary event predicate. Keeping this mapping next to
# EVENT_KINDS makes the Prolog fact -> Catala input schema conversion explicit.
EVENT_FIELDS = {
    pred: re.sub(r"_$", "_events", pred) for pred in EVENT_KINDS
}

# Unary categories whose grounded SARA fan-out is 0-or-1 per world. Keeping
# this beside EVENT_FIELDS makes the bounded Catala schema and both adapters
# share one authoritative list.
OPTIONAL_EVENT_FIELDS = {
    "itemize_deductions_events", "unemployment_compensation_agreement_events",
    "american_employer_events", "attending_classes_events", "blindness_events",
    "brother_events", "business_events", "business_trust_events",
    "daughter_events", "death_events", "disability_events",
    "educational_institution_events", "enrollment_events", "father_events",
    "hospital_events", "incarceration_events", "international_organization_events",
    "legal_separation_events", "medical_institution_events",
    "medical_patient_events", "migration_events", "mother_events",
    "nonresident_alien_events", "nurses_training_school_events",
    "penal_institution_events", "retirement_events", "sibling_events",
    "sister_events", "termination_events",
}

# Binary role predicates -> category-record field.
ROLE_FIELDS = {
    "agent_": "agents", "patient_": "patients", "start_": "starts",
    "end_": "ends", "amount_": "amounts", "purpose_": "purposes",
    "location_": "places", "means_": "media", "reason_": "reasons",
    "beneficiary_": "beneficiaries", "country_": "countries",
    "type_": "types", "destination_": "destinations",
}

# Role facts whose subject has no suitable unary category are represented as
# narrow binary relations.  Do not replace these with another catch-all event:
# its Cartesian payload is precisely what makes symbolic inputs explode.
ROLE_FACTS = {
    "agents": ("AgentFact", "agent_facts"),
    "patients": ("PatientFact", "patient_facts"),
    "starts": ("StartFact", "start_facts"),
    "ends": ("EndFact", "end_facts"),
    "amounts": ("AmountFact", "amount_facts"),
    "purposes": ("PurposeFact", "purpose_facts"),
    "places": ("PlaceFact", "place_facts"),
    "media": ("MediumFact", "medium_facts"),
    "reasons": ("ReasonFact", "reason_facts"),
    "beneficiaries": ("BeneficiaryFact", "beneficiary_facts"),
    "countries": ("CountryFact", "country_facts"),
    "types": ("TypeFact", "type_facts"),
    "destinations": ("DestinationFact", "destination_facts"),
}

# Fields retained by each category-specific Catala input record.  This is the
# semantic schema used by the statute, not a profile of mutation noise: a
# mutation may attach (say) a destination to a birth, but no translated rule
# can observe that role on a birth. Narrow records keep such irrelevant facts
# out of BOBCat's symbolic input altogether; observable uncategorized roles use
# the independent binary relations in ``ROLE_FACTS``.
EVENT_CATEGORY_ROLES = {
    "marriage_": ("agents", "starts", "ends"),
    "birth_": ("agents", "starts", "ends"),
    "death_": ("agents", "starts", "ends"),
    "income_": ("agents", "starts", "ends", "amounts", "purposes"),
    "payment_": ("agents", "patients", "starts", "ends", "amounts",
                 "purposes", "media", "beneficiaries"),
    "service_": ("agents", "patients", "starts", "ends", "purposes",
                 "places", "media", "types"),
    "residence_": ("agents", "patients", "starts", "ends"),
    "migration_": ("agents", "purposes", "destinations"),
    "retirement_": ("agents", "starts", "reasons"),
    "deduction_": ("agents", "starts", "amounts"),
    "enrollment_": ("agents", "patients", "starts", "ends"),
    "termination_": ("agents", "patients", "starts", "reasons"),
    "incarceration_": ("agents", "patients", "starts", "ends"),
    "legal_separation_": ("agents", "patients", "starts"),
    "joint_return_": ("agents", "starts", "ends"),
    "itemize_deductions_": (),
    "blindness_": ("agents", "starts"),
    "disability_": ("agents", "starts"),
    "attending_classes_": ("agents", "starts", "ends", "places"),
    "medical_patient_": ("agents", "patients", "starts", "ends"),
    "nonresident_alien_": ("agents", "starts", "ends"),
    "citizenship_": ("agents", "patients"),
    "son_": ("agents", "patients", "starts"),
    "daughter_": ("agents", "patients"),
    "father_": ("agents", "patients", "starts"),
    "mother_": ("agents", "patients", "starts"),
    "brother_": ("agents", "patients", "starts"),
    "sister_": ("agents", "patients", "starts"),
    "sibling_": ("agents", "patients"),
    "business_": ("agents", "starts", "types"),
    "business_trust_": ("agents", "starts", "ends"),
    "plan_": ("agents", "purposes", "beneficiaries"),
    "hospital_": ("agents",),
    "medical_institution_": ("agents",),
    "penal_institution_": ("agents",),
    "educational_institution_": ("agents",),
    "nurses_training_school_": ("agents",),
    "international_organization_": ("agents",),
    "american_employer_": ("agents",),
    "unemployment_compensation_agreement_": ("agents",),
}

# Category/role pairs whose grounded SARA worlds contain at most one value.
# Cardinality is pair-specific: a payment can have many starts while a
# retirement has at most one. Media and beneficiaries deliberately stay lists.
OPTIONAL_CATEGORY_ROLES = {
    ("marriage_", "ends"),
    ("birth_", "starts"), ("birth_", "ends"),
    ("death_", "starts"), ("death_", "ends"),
    ("income_", "agents"), ("income_", "ends"), ("income_", "purposes"),
    ("payment_", "ends"), ("payment_", "purposes"),
    ("service_", "ends"), ("service_", "purposes"), ("service_", "types"),
    ("residence_", "ends"),
    ("migration_", "agents"), ("migration_", "purposes"),
    ("migration_", "destinations"),
    ("retirement_", "agents"), ("retirement_", "starts"),
    ("retirement_", "reasons"),
    ("deduction_", "starts"), ("deduction_", "amounts"),
    ("enrollment_", "patients"), ("enrollment_", "starts"),
    ("enrollment_", "ends"),
    ("termination_", "agents"), ("termination_", "patients"),
    ("termination_", "starts"), ("termination_", "reasons"),
    ("incarceration_", "agents"), ("incarceration_", "patients"),
    ("incarceration_", "starts"), ("incarceration_", "ends"),
    ("legal_separation_", "agents"), ("legal_separation_", "patients"),
    ("legal_separation_", "starts"),
    ("joint_return_", "starts"), ("joint_return_", "ends"),
    ("blindness_", "starts"),
    ("disability_", "agents"), ("disability_", "starts"),
    ("attending_classes_", "agents"), ("attending_classes_", "starts"),
    ("attending_classes_", "ends"), ("attending_classes_", "places"),
    ("medical_patient_", "agents"), ("medical_patient_", "patients"),
    ("medical_patient_", "starts"), ("medical_patient_", "ends"),
    ("nonresident_alien_", "ends"),
    ("citizenship_", "agents"),
    ("daughter_", "agents"), ("daughter_", "patients"),
    ("father_", "starts"),
    ("mother_", "agents"), ("mother_", "patients"),
    ("brother_", "starts"),
    ("sister_", "agents"), ("sister_", "patients"), ("sister_", "starts"),
    ("sibling_", "patients"),
    ("business_", "starts"), ("business_", "types"),
    ("business_trust_", "ends"),
    ("plan_", "agents"), ("plan_", "purposes"),
    ("hospital_", "agents"), ("penal_institution_", "agents"),
    ("educational_institution_", "agents"),
    ("nurses_training_school_", "agents"),
    ("international_organization_", "agents"),
    ("american_employer_", "agents"),
    ("unemployment_compensation_agreement_", "agents"),
}

# The closed semantic vocabulary the statutes branch on.
PURPOSES = {
    "agricultural labor": "AgriculturalLabor",
    "domestic service": "DomesticService",
    "make provisions for employees in case of sickness": "ProvisionSickness",
    "make provisions for employees in case of accident disability":
        "ProvisionAccidentDisability",
    "make provisions for employees in case of death": "ProvisionDeath",
    "make provisions for employees or dependents":
        "ProvisionEmployeesOrDependents",
}
PLACES = {
    "usa": "Usa", "private home": "PrivateHome",
    "local college club": "LocalCollegeClub",
    "local chapter of a college fraternity": "LocalCollegeFraternityChapter",
    "local chapter of a college sorority": "LocalCollegeSororityChapter",
    "united states government": "UnitedStatesGovernment",
}
MEDIA = {"cash": "Cash"}

# Non-statute predicates a case may grant directly, e.g. `utils.pl`'s
# `total_wages_employer/6`, asserted by the two §3301 cases.
INJECTABLE_UTILS = {"total_wages_employer"}

# Argument positions that no translated consumer reads. Preserve arity (it is
# part of the Prolog predicate identity), but do not intern or carry a bogus
# semantic value for these slots. Positions are zero-based here.
IGNORED_INJECTION_POSITIONS = {
    "s151/5": {2}, "s152_b_2/4": {1}, "s152_d_2_H/6": {3},
    "s3306_b/8": {7}, "s63_c_3/4": {1}, "s63_d/4": {1},
    "s7703/4": {2}, "total_wages_employer/6": {2, 3},
    "s2_a/5": {1, 2, 3},
}

ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5}
SCHEDULE = {"a": "ScheduleA", "b": "ScheduleB", "c": "ScheduleC", "d": "ScheduleD"}


def is_var(tok: str) -> bool:
    """A Prolog query argument left unbound: `_` or a capitalised variable."""
    return tok == "_" or bool(re.match(r"^[A-Z_]", tok))


def money_arg(v: str) -> str:
    """A Prolog numeric literal in a query goal, as Catala money."""
    return f"(money of {int(v)})"


def opt_money_arg(v: str) -> str:
    """As money_arg, but an unbound argument becomes Absent."""
    return "Absent" if is_var(v) else f"Present content {money_arg(v)}"


def render_bracket(sym, rec, goal) -> str:
    """s1_<sched>_<roman>(Taxinc, Tax) -> Section1.BracketHolds."""
    _, sched, roman = goal["predicate"].split("_", 2)
    income, claimed = goal["args"]
    return (f"(output of S1.BracketHolds with {{"
            f" -- sched: S1.Schedule.{SCHEDULE[sched]}"
            f" -- index: {ROMAN[roman]}"
            f" -- taxable_income: {money_arg(income)}"
            f" -- claimed_tax: {money_arg(claimed)} }}).holds")


SUBPARA = {"A": "JointOrSurvivingSpouse", "B": "HeadOfHousehold",
           "C": "Unmarried", "D": "MarriedFilingSeparately"}


def render_s68_f(sym, rec, goal) -> str:
    """s68_f(Taxy) -> Section68.SuspendedHolds."""
    return (f"(output of S68.SuspendedHolds with {{"
            f" -- taxable_year: {int(goal['args'][0])} }}).holds")


def render_s68_subpara(sym, rec, goal) -> str:
    """s68_b_1_<X>(Taxp, ..., Aa, Taxy) -> Section68.SubparagraphHolds."""
    letter = goal["predicate"].split("_")[-1]
    args = goal["args"]
    taxpayer, claimed, year = args[0], args[-2], args[-1]
    return (f"(output of S68.SubparagraphHolds with {{"
            f" -- world: world -- injections: injections"
            f" -- taxpayer: {entity_lit(sym, taxpayer)}"
            f" -- taxable_year: {int(year)}"
            f" -- subparagraph: S68.FilingStatus.{SUBPARA[letter]}"
            f" -- claimed: {opt_money_arg(claimed)} }}).holds")


# Prolog query predicate -> how to render the Catala query for it.
# Filled in as sections land; see prolog_to_catala/sara/README.md.
PORTED: dict[str, dict] = {}
for _s in SCHEDULE:
    for _r in ROMAN:
        PORTED[f"s1_{_s}_{_r}/2"] = {"render": render_bracket, "uses": ["Section1 as S1"]}
PORTED["s68_f/1"] = {"render": render_s68_f, "uses": ["Section68 as S68"]}

def render_s63_c_7(sym, rec, goal) -> str:
    """s63_c_7_i(Taxy,Amount) / s63_c_7_ii(Taxy,Amount)."""
    year, claimed = goal["args"]
    clause_i = goal["predicate"].endswith("_i")
    return (f"(output of S63.SpecialRuleHolds with {{"
            f" -- taxable_year: {int(year)}"
            f" -- is_clause_i: {'true' if clause_i else 'false'}"
            f" -- claimed: {money_arg(claimed)} }}).holds")


def render_s63_c_2_C(sym, rec, goal) -> str:
    """s63_c_2_C(Taxy,Bassd)."""
    year, claimed = goal["args"]
    return (f"(output of S63.ResidualBasicHolds with {{"
            f" -- taxable_year: {int(year)}"
            f" -- claimed: {money_arg(claimed)} }}).holds")


def render_s63_c_2_B(sym, rec, goal) -> str:
    """s63_c_2_B(Taxp,Taxy,Bassd)."""
    taxpayer, year, claimed = goal["args"]
    return (f"(output of S63.HeadOfHouseholdBasicHolds with {{"
            f" -- status: (output of St.StatusDetermination with {{"
            f" -- world: world -- injections: injections"
            f" -- taxpayer: {entity_lit(sym, taxpayer)}"
            f" -- taxable_year: {int(year)} }}).status"
            f" -- taxable_year: {int(year)}"
            f" -- claimed: {money_arg(claimed)} }}).holds")


_S63 = ["Section63 as S63", "Section68 as St"]
PORTED["s63_c_7_i/2"] = {"render": render_s63_c_7, "uses": _S63}
PORTED["s63_c_7_ii/2"] = {"render": render_s63_c_7, "uses": _S63}
PORTED["s63_c_2_C/2"] = {"render": render_s63_c_2_C, "uses": _S63}
PORTED["s63_c_2_B/3"] = {"render": render_s63_c_2_B, "uses": _S63}

def render_s7703_a(sym, rec, goal) -> str:
    """s7703_a_1(Taxp,Spouse,Marriage,_,Taxy) / s7703_a_2(...) -- both are
    existential over the spouse and the marriage."""
    args = goal["args"]
    taxpayer, year = args[0], args[-1]
    field = "holds_a_1" if goal["predicate"].endswith("_1") else "holds_a_2"
    return (f"(output of S7703.MaritalStatusA with {{"
            f" -- world: world"
            f" -- taxpayer: {entity_lit(sym, taxpayer)}"
            f" -- taxable_year: {int(year)} }}).{field}")


PORTED["s7703_a_1/5"] = {"render": render_s7703_a, "uses": ["Section7703 as S7703"]}
PORTED["s7703_a_2/5"] = {"render": render_s7703_a, "uses": ["Section7703 as S7703"]}

KIN_ARGS = ("-- child_of: child_of -- sibling_of: sibling_of"
            " -- descendent_of: descendent_of"
            " -- stepsibling_of: stepsibling_of")


def render_s152_c_2(sym, rec, goal) -> str:
    """s152_c_2_A/5, s152_c_2_B/5, s152_c_2/4 -- the relationship tests."""
    dep, taxp = goal["args"][0], goal["args"][1]
    pred = goal["predicate"]
    field = ("holds_a" if pred.endswith("_A")
             else "holds_b" if pred.endswith("_B") else "holds")
    return (f"(output of S152.QualifyingChildRelationship with {{"
            f" -- injections: injections"
            f" -- dependant: {entity_lit(sym, dep)}"
            f" -- taxpayer: {entity_lit(sym, taxp)} {KIN_ARGS} }}).{field}")


def render_s152_c_3(sym, rec, goal) -> str:
    dep, taxp, year = goal["args"]
    return (f"(output of S152.AgeRequirement with {{"
            f" -- injections: injections -- world: world"
            f" -- dependant: {entity_lit(sym, dep)}"
            f" -- taxpayer: {entity_lit(sym, taxp)}"
            f" -- taxable_year: {int(year)}"
            f" -- descendent_of: descendent_of }}).holds")


def render_s152_c_1_E(sym, rec, goal) -> str:
    """s152_c_1_E(Dependent,Spouse,Taxy) -> Section152.NoJointReturn.

    The spouse is the goal's second argument and every case leaves it unbound,
    so the scope takes the whole §7703 spouse set. A *bound* spouse would be a
    different question -- one particular joint return rather than any -- and no
    case asks it.
    """
    dep, _spouse, year = goal["args"]
    return (f"(output of S152.NoJointReturn with {{"
            f" -- world: world -- dependant: {entity_lit(sym, dep)}"
            f" -- taxable_year: {int(year)}"
            f" -- spouses: (output of S7703.MaritalStatusA with {{"
            f" -- world: world -- taxpayer: {entity_lit(sym, dep)}"
            f" -- taxable_year: {int(year)} }}).spouses }}).holds")


def render_s152_b_2(sym, rec, goal) -> str:
    """s152_b_2(Dependent,S21,Spouse,Taxy) -> Section152.MarriedDependent.

    The third argument is the spouse, and the corpus binds it about as often as
    it leaves it free.  Discarding it made the port ask "is the dependant
    married to anyone", which is weaker than the Prolog and answers true on a
    joint return the named spouse never signed.  `S21` stays dropped: it is the
    joint return event itself, which the scope quantifies over, and no case
    binds it.
    """
    dep, spouse, year = goal["args"][0], goal["args"][2], goal["args"][-1]
    return (f"(output of S152.MarriedDependent with {{"
            f" -- injections: injections -- world: world"
            f" -- dependant: {entity_lit(sym, dep)}"
            f" -- spouse: {_opt_entity(sym, str(spouse))}"
            f" -- taxable_year: {int(year)} }}).holds")


def render_s152_d_1_B(sym, rec, goal) -> str:
    """s152_d_1_B(Dependent,Taxy) -> Section152.NoIncome.

    An unbound dependant is a different test, not a generator: `gross_income/3`
    sums the whole world and leaves the argument unbound.  See D34.
    """
    dep, year = goal["args"]
    unbound = "true" if is_var(str(dep)) else "false"
    return (f"(output of S152.NoIncome with {{"
            f" -- world: world -- injections: injections"
            f" -- dependant: {entity_lit(sym, dep)}"
            f" -- dependant_unbound: {unbound}"
            f" -- taxable_year: {int(year)} {KIN_ARGS} }}).holds")


def render_s152_c_1_B(sym, rec, goal) -> str:
    """s152_c_1_B(Dependent,S38,Taxp,Start,End,Taxy) -> Section152.SameAbode.

    The relationship window is the goal's own 4th and 5th arguments, not
    §152(c)(1)(A)'s kinship windows.  Every case leaves both unbound, and an
    unbound date is simply skipped by `latest/2` and `earliest/2`, so the span
    is then the residences intersected with the taxable year and nothing else.

    Routing this through `QualifyingChild.abode` instead quantified over the
    (c)(1)(A) windows, which asks whether the pair are *related* as well as
    sharing an abode.  On the corpus the two agree, because the cases that ask
    (c)(1)(B) are about relatives; off it they do not, and a taxpayer sharing
    an abode with themselves made the port say no where SARA says yes.
    """
    dep, _abode, taxp, start, end, year = goal["args"]
    return (f"(output of S152.SameAbode with {{ -- world: world"
            f" -- dependant: {entity_lit(sym, dep)}"
            f" -- taxpayer: {entity_lit(sym, taxp)}"
            f" -- taxable_year: {int(year)}"
            f" -- relationship: K.Window {{ -- starts_on: {opt_date(start)}"
            f" -- ends_on: {opt_date(end)} }} }}).holds")


KIN_ARGS_ALL = (KIN_ARGS
                + " -- stepparent_of: stepparent_of"
                  " -- child_in_law_of: child_in_law_of"
                  " -- parent_in_law_of: parent_in_law_of"
                  " -- sibling_in_law_of: sibling_in_law_of")


def _qrr(sym, dep, taxp, windows_h="[]") -> str:
    """A call to §152(d)(2)(A)-(G). (H) is passed in, empty unless asked for."""
    return (f"(output of S152.QualifyingRelativeRelationship with {{"
            f" -- dependant: {entity_lit(sym, dep)}"
            f" -- taxpayer: {entity_lit(sym, taxp)}"
            f" -- windows_h: {windows_h} {KIN_ARGS_ALL} }})")


def _d2_field(pred: str) -> str:
    return ("windows" if pred == "s152_d_2"
            else "windows_" + pred.rsplit("_", 1)[1].lower())


def render_s152_d_2(sym, rec, goal) -> str:
    """s152_d_2_A/4 .. s152_d_2_G/4 and the s152_d_2/5 disjunction.

    Plain existence: does the subparagraph yield any window at all?  Two of
    these cases -- (D) and (G) -- instead bind the window and constrain it,
    which is the conjunctive branch below.
    """
    goals = rec["test"]["goals"]
    if len(goals) > 1:
        return _render_s152_d_2_window(sym, rec, goal)
    dep, taxp = goal["args"][0], goal["args"][1]
    return f"((number of {_qrr(sym, dep, taxp)}.{_d2_field(goal['predicate'])}) > 0)"


def _render_s152_d_2_window(sym, rec, goal) -> str:
    """The conjunctive form:

        s152_d_2_X(Dep,Taxp,Start,End), var(End),
        first_day_year(Y,First_day), is_before(Start,First_day)

    which asks for a solution whose window is still open (`End` unbound) and
    began on or before 1 January of Y -- a question about *which* windows the
    subparagraph yields, not merely whether it yields one.
    """
    goals = rec["test"]["goals"]
    shape = [g["predicate"] for g in goals]
    assert shape == [goal["predicate"], "var", "first_day_year", "is_before"], shape
    assert goals[1]["args"] == [goal["args"][3]]
    assert goals[3]["args"] == [goal["args"][2], goals[2]["args"][1]]
    year = int(goals[2]["args"][0])
    dep, taxp = goal["args"][0], goal["args"][1]
    return (f"(S152.open_window_before of"
            f" {_qrr(sym, dep, taxp)}.{_d2_field(goal['predicate'])},"
            f" (W.first_day_year of {year}))")


def render_s152_d_2_H(sym, rec, goal) -> str:
    """s152_d_2_H(Dependent,Taxp,Taxy,S143,Start_day,End_day)."""
    dep, taxp, year = goal["args"][0], goal["args"][1], goal["args"][2]
    dep_gen = "true" if is_var(str(dep)) else "false"
    return (f"(output of S152.MemberOfHousehold with {{"
            f" -- injections: injections -- world: world"
            f" -- dependant: {entity_lit(sym, dep)}"
            f" -- taxpayer: {entity_lit(sym, taxp)}"
            # the goal names the taxpayer, so this is (H) as a checker
            f" -- taxpayer_generated: false"
            # ... but it may leave the dependant to be generated; see D50
            f" -- dependant_generated: {dep_gen}"
            f" -- taxable_year: {int(year)} }}).holds")


def render_s152_c_1(sym, rec, goal) -> str:
    """s152_c_1(Dependent,Taxp,Taxy) -- the whole (c)(1) conjunction."""
    dep, taxp, year = goal["args"]
    return (f"(output of S152.QualifyingChild with {{"
            f" -- injections: injections -- world: world"
            f" -- dependant: {entity_lit(sym, dep)}"
            f" -- taxpayer: {entity_lit(sym, taxp)}"
            f" -- taxable_year: {int(year)} {KIN_ARGS} }}).holds")


def render_s152_d_1_D(sym, rec, goal) -> str:
    """s152_d_1_D(Dependent,Taxy) -- not a qualifying child of any taxpayer."""
    dep, year = goal["args"]
    return (f"(not (output of S152.AnyQualifyingChildTaxpayer with {{"
            f" -- injections: injections -- world: world"
            f" -- dependant: {entity_lit(sym, dep)}"
            f" -- taxable_year: {int(year)} {KIN_ARGS} }}).holds)")


def render_s152_a(sym, rec, goal) -> str:
    """s152_a(Dependent,Taxp,Taxy,Start_relationship,End_relationship)."""
    dep, taxp, year = goal["args"][0], goal["args"][1], goal["args"][2]
    return (f"(output of S152.Dependent with {{"
            f" -- injections: injections -- world: world"
            f" -- dependant: {entity_lit(sym, dep)}"
            f" -- taxpayer: {entity_lit(sym, taxp)}"
            # the goal names the taxpayer, so §152(d)(2)(H) runs as a checker
            f" -- taxpayer_generated: false"
            f" -- dependant_generated: {'true' if is_var(str(dep)) else 'false'}"
            f" -- taxable_year: {int(year)} {KIN_ARGS_ALL} }}).holds")


def render_s152_b_1(sym, rec, goal) -> str:
    """s152_b_1(Taxp,Otaxp,Taxy), always asked with Otaxp unbound."""
    person, year = goal["args"][0], goal["args"][2]
    return (f"(output of S152.Ineligible with {{"
            f" -- injections: injections -- world: world"
            f" -- person: {entity_lit(sym, person)}"
            f" -- taxable_year: {int(year)} {KIN_ARGS_ALL} }}).holds")


_S2 = ["Section2 as S2", "Section151 as S151", "Section152 as S152",
       "Section7703 as S7703"]


def _s2(sym, scope: str, taxpayer: str, year, extra: str = "",
        with_world: bool = True) -> str:
    w = " -- injections: injections -- world: world" if with_world else " -- world: world"
    return (f"(output of S2.{scope} with {{{w}"
            f" -- taxpayer: {entity_lit(sym, taxpayer)}"
            f" -- taxable_year: {int(year)}{extra} {KIN_ARGS_ALL} }})")


def _opt_entity(sym, tok: str) -> str:
    return "Absent" if is_var(tok) else f"Present content {entity_lit(sym, tok)}"


def render_s2_a_1_A(sym, rec, goal) -> str:
    taxpayer, year = goal["args"][0], goal["args"][4]
    return (f"(output of S2.SpouseDiedRecently with {{"
            f" -- world: world -- taxpayer: {entity_lit(sym, taxpayer)}"
            f" -- taxable_year: {int(year)} }}).holds")


def render_s2_a_1_B(sym, rec, goal) -> str:
    taxpayer, year = goal["args"][0], goal["args"][3]
    return _s2(sym, "MaintainsHomeForChild", taxpayer, year) + ".holds"


def render_s2_a_2_A(sym, rec, goal) -> str:
    taxpayer, year = goal["args"][0], goal["args"][4]
    return (f"(output of S2.Remarried with {{"
            f" -- world: world -- taxpayer: {entity_lit(sym, taxpayer)}"
            f" -- taxable_year: {int(year)} }}).holds")


def render_s2_a_2_B(sym, rec, goal) -> str:
    taxpayer, spouse, year = goal["args"]
    return (f"(output of S2.JointReturnPossible with {{"
            f" -- world: world -- taxpayer: {entity_lit(sym, taxpayer)}"
            f" -- spouse: {_opt_entity(sym, spouse)}"
            f" -- taxable_year: {int(year)} }}).holds")


def render_s2_a(sym, rec, goal) -> str:
    taxpayer, year = goal["args"][0], goal["args"][-1]
    return _s2(sym, "SurvivingSpouse", taxpayer, year) + ".holds"


def render_s2_b_1_A_i(sym, rec, goal) -> str:
    """s2_b_1_A_i(Taxp,Dependent,Taxy) -- the taxpayer is left unbound."""
    taxpayer, dependant, year = goal["args"]
    return (f"(output of S2.QualifyingChildClause with {{"
            f" -- injections: injections -- world: world"
            f" -- dependant: {entity_lit(sym, dependant)}"
            f" -- taxpayer: {_opt_entity(sym, taxpayer)}"
            f" -- taxable_year: {int(year)} {KIN_ARGS} }}).holds")


def render_s2_b_1_A_i_I(sym, rec, goal) -> str:
    dependant, year = goal["args"]
    return (f"(output of S2.DependentMarried with {{"
            f" -- injections: injections -- world: world"
            f" -- dependant: {entity_lit(sym, dependant)}"
            f" -- taxable_year: {int(year)} {KIN_ARGS} }}).holds")


def render_s2_b_1_A_i_II(sym, rec, goal) -> str:
    """s152_b_2(Dependent,_,Spouse,Taxy): the third argument is the spouse."""
    dependant, spouse, year = goal["args"]
    return (f"(output of S2.DependentJointReturnWith with {{"
            f" -- injections: injections -- world: world"
            f" -- dependant: {entity_lit(sym, dependant)}"
            f" -- spouse: {entity_lit(sym, spouse)}"
            f" -- taxable_year: {int(year)} }}).holds")


def render_s2_b_1_A_ii(sym, rec, goal) -> str:
    taxpayer, dependant, year = goal["args"]
    return (f"(output of S2.OtherDependentClause with {{"
            f" -- injections: injections -- world: world"
            f" -- dependant: {entity_lit(sym, dependant)}"
            f" -- taxpayer: {_opt_entity(sym, taxpayer)}"
            f" -- taxable_year: {int(year)} {KIN_ARGS_ALL} }}).holds")


def render_s2_b_1_A(sym, rec, goal) -> str:
    taxpayer, year = goal["args"][0], goal["args"][3]
    return _s2(sym, "HouseholdForDependent", taxpayer, year) + ".holds"


def render_s2_b_1_B(sym, rec, goal) -> str:
    taxpayer, year = goal["args"][0], goal["args"][4]
    return _s2(sym, "HouseholdForParent", taxpayer, year) + ".holds"


def render_s2_b_1(sym, rec, goal) -> str:
    taxpayer, year = goal["args"][0], goal["args"][3]
    return _s2(sym, "HeadOfHouseholdOne", taxpayer, year) + ".holds"


def render_s2_b_2_A(sym, rec, goal) -> str:
    taxpayer, spouse, year = goal["args"][0], goal["args"][1], goal["args"][4]
    return (f"(output of S2.LegallySeparatedFrom with {{"
            f" -- world: world -- taxpayer: {entity_lit(sym, taxpayer)}"
            f" -- spouse: {entity_lit(sym, spouse)}"
            f" -- taxable_year: {int(year)} }}).holds")


def render_s2_b_2_B(sym, rec, goal) -> str:
    taxpayer, spouse, year = goal["args"]
    return (f"(output of S2.SpouseNonresidentAlien with {{"
            f" -- world: world -- taxpayer: {entity_lit(sym, taxpayer)}"
            f" -- spouse: {_opt_entity(sym, spouse)}"
            f" -- taxable_year: {int(year)} }}).holds")


def render_s2_b_2_C(sym, rec, goal) -> str:
    taxpayer, _marriage, spouse, year = goal["args"]
    return (f"(output of S2.SpouseDiedInYear with {{"
            f" -- world: world -- taxpayer: {entity_lit(sym, taxpayer)}"
            f" -- spouse: {_opt_entity(sym, spouse)}"
            f" -- taxable_year: {int(year)} }}).holds")


def render_s2_b_3_A(sym, rec, goal) -> str:
    taxpayer, year = goal["args"][0], goal["args"][1]
    return (f"(output of S2.NonresidentAlienTaxpayer with {{"
            f" -- world: world -- taxpayer: {entity_lit(sym, taxpayer)}"
            f" -- taxable_year: {int(year)} }}).holds")


def render_s2_b_3_B(sym, rec, goal) -> str:
    taxpayer, dependant, year = goal["args"]
    return _s2(sym, "HouseholdMemberOnly", taxpayer, year,
               f" -- dependant: {_opt_entity(sym, dependant)}") + ".holds"


def render_s2_b(sym, rec, goal) -> str:
    taxpayer, dependant, year = goal["args"]
    return _s2(sym, "HeadOfHousehold", taxpayer, year,
               f" -- dependant: {_opt_entity(sym, dependant)}") + ".holds"


_S63_FULL = ["Section63 as S63", "Section68 as St", "Section151 as S151",
             "Section152 as S152", "Section7703 as S7703", "Section68 as S68"]


def render_s63_ab(sym, rec, goal) -> str:
    """s63_a(Taxp,Taxy,Taxinc,_,_) and s63_b(Taxp,Taxy,Taxinc,_)."""
    args = goal["args"]
    taxpayer, year, claimed = args[0], int(args[1]), args[2]
    clause = "SubsectionA" if goal["predicate"] == "s63_a" else "SubsectionB"
    return (f"(output of S63.TaxableIncomeHolds with {{"
            f" -- world: world -- injections: injections"
            f" -- taxpayer: {entity_lit(sym, taxpayer)}"
            f" -- taxable_year: {year}"
            f" -- clause: S63.IncomeClause.{clause}"
            f" -- claimed: {money_arg(claimed)} {KIN_ARGS_ALL} }}).holds")


def render_s63_c_1(sym, rec, goal) -> str:
    """s63_c_1(Taxp,Taxy,Standed) and s63_c(Taxp,Taxy,Standed)."""
    taxpayer, year, claimed = goal["args"]
    return (f"(output of S63.StandardDeductionHolds with {{"
            f" -- world: world -- injections: injections"
            f" -- taxpayer: {entity_lit(sym, taxpayer)}"
            f" -- taxable_year: {int(year)}"
            f" -- claimed: {money_arg(claimed)} {KIN_ARGS_ALL} }}).holds")


def render_s63_d_2(sym, rec, goal) -> str:
    """s63_d_2(Taxp,Ded151,Taxy) -- the second argument is §151's list of
    exemption amounts, written as a Prolog list literal."""
    taxpayer, claimed, year = goal["args"]
    items = [x for x in claimed.strip("[]").split(",") if x.strip()]
    lst = "; ".join(money_arg(x.strip()) for x in items)
    return (f"(output of S63.ExemptionListHolds with {{"
            f" -- world: world -- injections: injections"
            f" -- taxpayer: {entity_lit(sym, taxpayer)}"
            f" -- taxable_year: {int(year)}"
            f" -- claimed: [{lst}] {KIN_ARGS_ALL} }}).holds")


def render_s68_a_1_conj(sym, rec, goal) -> str:
    """s68_b(Taxp,Aa,Taxy), gross_income(Taxp,Taxy,Agi), s68_a_1(Agi,Aa,R)."""
    goals = rec["test"]["goals"]
    shape = [g["predicate"] for g in goals]
    assert shape == ["s68_b", "gross_income", "s68_a_1"], shape
    taxpayer, aa_var, year = goals[0]["args"]
    assert goals[1]["args"] == [taxpayer, year, goals[2]["args"][0]]
    assert goals[2]["args"][1] == aa_var
    claimed = goals[2]["args"][2]
    return (f"(output of S68.ReductionOneForTaxpayer with {{"
            f" -- world: world -- injections: injections"
            f" -- taxpayer: {entity_lit(sym, taxpayer)}"
            f" -- taxable_year: {int(year)}"
            f" -- claimed: {money_arg(claimed)} }}).holds")


_S151 = ["Section151 as S151", "Section152 as S152", "Section7703 as S7703"]


def _numeric(v: str) -> bool:
    try:
        int(v)
        return True
    except ValueError:
        return False


def _s151(sym, scope: str, taxpayer: str, year, extra: str = "") -> str:
    return (f"(output of S151.{scope} with {{"
            f" -- injections: injections -- world: world"
            f" -- taxpayer: {entity_lit(sym, taxpayer)}"
            f" -- taxable_year: {int(year)}{extra} {KIN_ARGS_ALL} }})")


def render_s151_a(sym, rec, goal) -> str:
    """s151_a(Taxp,S2,Taxy) -- the total deduction for personal exemptions."""
    taxpayer, claimed, year = goal["args"]
    return f"{_s151(sym, 'Personal', taxpayer, year)}.total = {money_arg(claimed)}"


def render_s151_b(sym, rec, goal) -> str:
    """s151_b/4 is the spouse's exemption; s151_b/3 is the taxpayer's own.

    `s151_b_neg` asks `s151_b(alice,bob,2015)` -- the /3 form with an *atom*
    where the exemption amount goes. `s151_d` only ever binds a number, so the
    unification cannot succeed. The port says so rather than pretending the
    argument is money.
    """
    args = goal["args"]
    if len(args) == 3:
        taxpayer, claimed, year = args
        if not _numeric(claimed):
            return ("false # s151_b/3 with a non-numeric exemption amount:"
                    " s151_d never binds an atom, so this cannot unify")
        return (f"{_s151(sym, 'Individual', taxpayer, year)}.exemption_amount"
                f" = {money_arg(claimed)}")
    taxpayer, spouse, claimed, year = args
    return _s151(sym, "SpouseExemptionHolds", taxpayer, year,
                 f" -- spouse: {entity_lit(sym, spouse)}"
                 f" -- claimed: {opt_money_arg(claimed)}") + ".holds"


def render_s151_c(sym, rec, goal) -> str:
    """s151_c(Taxp,S24,Ea,Taxy)."""
    taxpayer, dependant, claimed, year = goal["args"]
    return _s151(sym, "DependentExemptionHolds", taxpayer, year,
                 f" -- dependant: {entity_lit(sym, dependant)}"
                 f" -- claimed: {opt_money_arg(claimed)}") + ".holds"


def render_s151_d_1(sym, rec, goal) -> str:
    """s151_d_1(Ea) -- the $2,000 constant."""
    (claimed,) = goal["args"]
    return f"(S151.exemption_base = {money_arg(claimed)})"


def render_s151_d_2(sym, rec, goal) -> str:
    """s151_d_2(Taxp,Otaxp,Ea,Taxy), always asked with Otaxp unbound."""
    taxpayer, _otaxp, claimed, year = goal["args"]
    return _s151(sym, "DisallowedHolds", taxpayer, year,
                 f" -- claimed: {money_arg(claimed)}") + ".holds"


def render_s151_d_3(sym, rec, goal) -> str:
    """s151_d_3_A(Taxp,Agi,Aa,Ap,Ein,Ea,Taxy) and
    s151_d_3_B(Ap,Taxp,Agi,Taxy,Aa)."""
    args = goal["args"]
    if goal["predicate"].endswith("_A"):
        taxpayer, year = args[0], args[6]
        extra = (f" -- exemption_in: {money_arg(args[4])}"
                 f" -- claimed: {opt_money_arg(args[5])}"
                 f" -- claimed_percentage: Absent")
        field = "holds_a"
    else:
        taxpayer, year = args[1], args[3]
        pct = ("Absent" if is_var(args[0])
               else f"Present content {int(args[0])}")
        extra = (f" -- exemption_in: S151.exemption_base"
                 f" -- claimed: Absent"
                 f" -- claimed_percentage: {pct}")
        field = "holds_b"
    return _s151(sym, "PhaseoutHolds", taxpayer, year, extra) + f".{field}"


def render_s151_d_5(sym, rec, goal) -> str:
    """s151_d_5(Ea,Taxy)."""
    claimed, year = goal["args"]
    return (f"(output of S151.SuspendedHolds with {{"
            f" -- taxable_year: {int(year)}"
            f" -- claimed: {money_arg(claimed)} }}).holds")


_S152 = ["Section152 as S152", "Section7703 as S7703"]
PORTED["s152_c_2_A/5"] = {"render": render_s152_c_2, "uses": _S152}
PORTED["s152_c_2_B/5"] = {"render": render_s152_c_2, "uses": _S152}
PORTED["s152_c_2/4"] = {"render": render_s152_c_2, "uses": _S152}
PORTED["s152_c_3/3"] = {"render": render_s152_c_3, "uses": _S152}
PORTED["s152_c_1_E/3"] = {"render": render_s152_c_1_E, "uses": _S152}
PORTED["s152_b_2/4"] = {"render": render_s152_b_2, "uses": _S152}
PORTED["s152_d_1_B/2"] = {"render": render_s152_d_1_B, "uses": _S152}
PORTED["s152_c_1_B/6"] = {"render": render_s152_c_1_B, "uses": _S152}
# (A)-(G): plain existence, except (D) and (G), which also appear in a
# window-constrained conjunctive form that `render_s152_d_2` dispatches on.
for _k in ("s152_d_2_A/4", "s152_d_2_B/4", "s152_d_2_C/4", "s152_d_2_D/4",
           "s152_d_2_E/5", "s152_d_2_F/5", "s152_d_2_G/4", "s152_d_2/5"):
    PORTED[_k] = {"render": render_s152_d_2, "uses": _S152, "multi": True}
PORTED["s152_d_2_H/6"] = {"render": render_s152_d_2_H, "uses": _S152}
PORTED["s152_c_1/3"] = {"render": render_s152_c_1, "uses": _S152}
PORTED["s152_d_1_D/2"] = {"render": render_s152_d_1_D, "uses": _S152}
PORTED["s152_a/5"] = {"render": render_s152_a, "uses": _S152}
PORTED["s152_b_1/3"] = {"render": render_s152_b_1, "uses": _S152}
PORTED["s151_a/3"] = {"render": render_s151_a, "uses": _S151}
PORTED["s151_b/3"] = {"render": render_s151_b, "uses": _S151}
PORTED["s151_b/4"] = {"render": render_s151_b, "uses": _S151}
PORTED["s151_c/4"] = {"render": render_s151_c, "uses": _S151}
PORTED["s151_d_1/1"] = {"render": render_s151_d_1, "uses": _S151}
PORTED["s151_d_2/4"] = {"render": render_s151_d_2, "uses": _S151}
PORTED["s151_d_3_A/7"] = {"render": render_s151_d_3, "uses": _S151}
PORTED["s151_d_3_B/5"] = {"render": render_s151_d_3, "uses": _S151}
PORTED["s151_d_5/2"] = {"render": render_s151_d_5, "uses": _S151}
PORTED["s63_a/5"] = {"render": render_s63_ab, "uses": _S63_FULL}
PORTED["s63_b/4"] = {"render": render_s63_ab, "uses": _S63_FULL}
PORTED["s63_c_1/3"] = {"render": render_s63_c_1, "uses": _S63_FULL}
PORTED["s63_c/3"] = {"render": render_s63_c_1, "uses": _S63_FULL}
PORTED["s63_d_2/3"] = {"render": render_s63_d_2, "uses": _S63_FULL}
PORTED["s2_a_1_A/5"] = {"render": render_s2_a_1_A, "uses": _S2}
PORTED["s2_a_1_B/4"] = {"render": render_s2_a_1_B, "uses": _S2}
PORTED["s2_a_2_A/5"] = {"render": render_s2_a_2_A, "uses": _S2}
PORTED["s2_a_2_B/3"] = {"render": render_s2_a_2_B, "uses": _S2}
PORTED["s2_a/3"] = {"render": render_s2_a, "uses": _S2}
PORTED["s2_b_1_A_i/3"] = {"render": render_s2_b_1_A_i, "uses": _S2}
PORTED["s2_b_1_A_i_I/2"] = {"render": render_s2_b_1_A_i_I, "uses": _S2}
PORTED["s2_b_1_A_i_II/3"] = {"render": render_s2_b_1_A_i_II, "uses": _S2}
PORTED["s2_b_1_A_ii/3"] = {"render": render_s2_b_1_A_ii, "uses": _S2}
PORTED["s2_b_1_A/4"] = {"render": render_s2_b_1_A, "uses": _S2}
PORTED["s2_b_1_B/5"] = {"render": render_s2_b_1_B, "uses": _S2}
PORTED["s2_b_1/4"] = {"render": render_s2_b_1, "uses": _S2}
PORTED["s2_b_2_A/5"] = {"render": render_s2_b_2_A, "uses": _S2}
PORTED["s2_b_2_B/3"] = {"render": render_s2_b_2_B, "uses": _S2}
PORTED["s2_b_2_C/4"] = {"render": render_s2_b_2_C, "uses": _S2}
PORTED["s2_b_3_A/3"] = {"render": render_s2_b_3_A, "uses": _S2}
PORTED["s2_b_3_B/3"] = {"render": render_s2_b_3_B, "uses": _S2}
PORTED["s2_b/3"] = {"render": render_s2_b, "uses": _S2}

def render_s7703_b(sym, rec, goal) -> str:
    """s7703_b_1(Taxp,Household,Dependent,Taxy), s7703_b_2(Taxp,Household,Cost,Taxy),
    s7703_b_3(Taxp,Spouse,Household,Taxy)."""
    pred = goal["predicate"]
    args = goal["args"]
    year = int(args[-1])
    taxpayer = entity_lit(sym, args[0])
    if pred.endswith("_1"):
        # the household is left unbound in the cases; every qualifying-child
        # dependant is a candidate, so the scope is asked over each household
        # the taxpayer resides at. Rendered as an existential in Catala.
        return (f"(exists h among (map each e among (list of ev among world.residence_events"
                f" such that ev.agents contains {taxpayer}) to e)"
                f" such that (exists hh among h.patients such that"
                f" (output of S7703.LivingApartOne with {{"
                f" -- world: world -- taxpayer: {taxpayer}"
                f" -- household: hh -- taxable_year: {year}"
                # `QualifyingChildrenOf`, not the raw kinship list: the
                # §152(c) age and support tests must apply here too.
                f" -- qualifying_dependants: (output of S152.QualifyingChildrenOf"
                f" with {{ -- injections: injections -- world: world"
                f" -- taxpayer: {taxpayer} -- taxable_year: {year}"
                f" {KIN_ARGS} }}).children }}).holds))")
    if pred.endswith("_2"):
        household = entity_lit(sym, args[1])
        return (f"(output of S7703.LivingApartTwo with {{"
                f" -- world: world -- taxpayer: {taxpayer}"
                f" -- household: {household} -- taxable_year: {year} }}).holds")
    household = entity_lit(sym, args[2])
    return (f"((output of S7703.MaritalStatusA with {{"
            f" -- world: world -- taxpayer: {taxpayer}"
            f" -- taxable_year: {year} }}).married"
            f" and (output of S7703.LivingApartThree with {{"
            f" -- world: world"
            f" -- spouse: (match (output of S7703.MaritalStatusA with {{"
            f" -- world: world -- taxpayer: {taxpayer}"
            f" -- taxable_year: {year} }}).spouse with pattern"
            f" -- Absent: {taxpayer} -- Present content sp: sp)"
            f" -- household: {household} -- taxable_year: {year} }}).holds)")


for _p in ("s7703_b_1/4", "s7703_b_2/4", "s7703_b_3/4"):
    PORTED[_p] = {"render": render_s7703_b,
                  "uses": ["Section7703 as S7703", "Section152 as S152"]}

# ---- filing-status plumbing shared by the §1/§63/§68 query renderers ----

def status_expr(sym, taxpayer: str, year: int) -> str:
    return (f"(output of St.StatusDetermination with {{ -- world: world"
            f" -- injections: injections"
            f" -- taxpayer: {entity_lit(sym, taxpayer)}"
            f" -- taxable_year: {year} }})")


def spouses_expr(sym, taxpayer: str, year: int) -> str:
    """Every §7703(a) spouse. `s7703(Taxp,Spouse,_,Taxy)` is a generator and
    the goals after it backtrack over it; taking the first is a narrower
    question. See D71."""
    return (f"(output of S7703.MaritalStatusA with {{ -- world: world"
            f" -- taxpayer: {entity_lit(sym, taxpayer)}"
            f" -- taxable_year: {year} }}).spouses")


def s151b_exempt_spouses_expr(sym, taxpayer: str, year: int) -> str:
    """The spouses `s151_b_applies(Taxp,Spouse,Taxy)` holds for — §63(f)'s
    spouse-exemption guard, as a *list*.

    Every case in the corpus that reaches this *injects* the conclusion, so
    reading only the injections agreed on all 374.  SARA also derives it
    (`section151.pl:70`), and a generated world that injects nothing then had
    every spouse exemption reported absent — §63(f)(1)(B) and (2)(B) came out
    false for a spouse SARA grants.  `Section151.Individual` derives the set,
    as `exempt_spouses`.

    A list rather than a boolean because `s63_f_1_B(Taxp,Spouse,Taxy)` carries
    one `Spouse` through the whole clause: the person §151(b) allows and the
    person over 65 are the same person, and testing the two halves against
    different spouses gave a couple filing jointly a $600 entitlement SARA
    never grants.  See D80.  It is built here rather than in Section63 for the
    query surfaces, which reach §151's dependencies only through the case.
    """
    ent = entity_lit(sym, taxpayer)
    indiv = (f"(output of S151.Individual with {{"
             f" -- injections: injections -- world: world"
             f" -- taxpayer: {ent} -- taxable_year: {year}"
             f" {KIN_ARGS_ALL} }})")
    # `s151_b_applies(Taxp,Spouse,Taxy)`: match the taxpayer in the first
    # argument only, else a grant made to the spouse in their own right also
    # applies in reverse.  An unbound spouse argument admits every §7703 spouse.
    granted = (f"(combine all r among (map each inj among"
               f" (W.injections_for_3_13 of injections,"
               f" P.pred_s151_b_applies_3, {ent}.id, W.num_key of {year})"
               f" to (match (W.injection_entity of inj, 2) with pattern"
               f" -- Absent: {indiv}.all_spouses"
               f" -- Present content sp: [sp]))"
               f" in acc initially [] with acc ++ r)")
    # A grant not declared discontiguous replaces §151(b)'s own clause: only
    # its rows hold, so skip the derivation entirely (D22, arity-3 guard).
    return (f"(if (W.pred_overridden of injections,"
            f" P.pred_s151_b_applies_3) then {granted}"
            f" else ({granted} ++ {indiv}.exempt_spouses))")


_AGED = {"s63_f_1_A": "AgedSelf", "s63_f_1_B": "AgedSpouse",
         "s63_f_2_A": "BlindSelf", "s63_f_2_B": "BlindSpouse"}


def render_s63_f_clause(sym, rec, goal) -> str:
    args = goal["args"]
    taxpayer, year = args[0], int(args[-1])
    st = status_expr(sym, taxpayer, year)
    return (f"(output of S63.AgedBlindClauseHolds with {{"
            f" -- world: world -- injections: injections"
            f" -- taxpayer: {entity_lit(sym, taxpayer)}"
            f" -- taxable_year: {year}"
            f" -- married: {st}.married"
            f" -- surviving_spouse: {st}.surviving_spouse"
            f" -- exempt_spouses: {s151b_exempt_spouses_expr(sym, taxpayer, year)}"
            f" -- clause: S63.AgedBlindClause.{_AGED[goal['predicate']]} }}).holds")


def render_s63_f_3(sym, rec, goal) -> str:
    taxpayer, year, claimed = goal["args"][0], int(goal["args"][1]), goal["args"][2]
    st = status_expr(sym, taxpayer, year)
    return (f"(output of S63.HigherAmountHolds with {{"
            f" -- married: {st}.married"
            f" -- surviving_spouse: {st}.surviving_spouse"
            f" -- claimed: {money_arg(claimed)} }}).holds")


def render_s63_c_3(sym, rec, goal) -> str:
    """s63_c_3(Taxp, Addsd, Taxy) -- amount is the *second* argument."""
    taxpayer, claimed, year = goal["args"][0], goal["args"][1], int(goal["args"][2])
    st = status_expr(sym, taxpayer, year)
    return (f"(output of S63.AdditionalDeductionHolds with {{"
            f" -- world: world -- injections: injections"
            f" -- taxpayer: {entity_lit(sym, taxpayer)}"
            f" -- taxable_year: {year}"
            f" -- married: {st}.married"
            f" -- surviving_spouse: {st}.surviving_spouse"
            f" -- exempt_spouses: {s151b_exempt_spouses_expr(sym, taxpayer, year)}"
            f" -- claimed: {money_arg(claimed)} }}).holds")


def render_s63_d(sym, rec, goal) -> str:
    """s63_d(Taxp, Itemded, Total_amount, Taxy)."""
    taxpayer, claimed, year = goal["args"][0], goal["args"][2], int(goal["args"][3])
    return (f"(output of S63.ItemizedTotalHolds with {{"
            f" -- world: world -- taxpayer: {entity_lit(sym, taxpayer)}"
            f" -- taxable_year: {year}"
            f" -- claimed: {opt_money_arg(claimed)} }}).holds")


_INELIG = {"s63_c_6_A": "ClauseA", "s63_c_6_B": "ClauseB", "s63_c_6_D": "ClauseD"}


def render_s63_c_6(sym, rec, goal) -> str:
    taxpayer, year = goal["args"][0], int(goal["args"][-1])
    st = status_expr(sym, taxpayer, year)
    return (f"(output of S63.NotEligibleClauseHolds with {{"
            f" -- world: world -- taxpayer: {entity_lit(sym, taxpayer)}"
            f" -- taxable_year: {year}"
            f" -- married: {st}.married"
            f" -- joint_return: {st}.joint_return"
            f" -- spouses: {spouses_expr(sym, taxpayer, year)}"
            f" -- clause: S63.IneligibleClause.{_INELIG[goal['predicate']]} }}).holds")


def render_s63_c_5(sym, rec, goal) -> str:
    """s63_c_5(Taxp, S45, Grossinc, Taxy, Bassd)."""
    args = goal["args"]
    taxpayer, year, claimed = args[0], int(args[3]), args[4]
    return (f"(output of S63.DependentCapHolds with {{"
            f" -- world: world -- injections: injections"
            f" -- taxpayer: {entity_lit(sym, taxpayer)}"
            f" -- taxable_year: {year}"
            f" -- claimed: {opt_money_arg(claimed)} {KIN_ARGS_ALL} }}).holds")


def render_s63_c_2_A(sym, rec, goal) -> str:
    taxpayer, year = goal["args"][0], int(goal["args"][-1])
    st = status_expr(sym, taxpayer, year)
    clause_i = goal["predicate"].endswith("_i")
    return (f"(output of S63.DoubledBasicHolds with {{"
            f" -- married: {st}.married"
            f" -- joint_return: {st}.joint_return"
            f" -- surviving_spouse: {st}.surviving_spouse"
            f" -- is_clause_i: {'true' if clause_i else 'false'} }}).holds")


_SUBSEC = {"s1_a": "ScheduleA", "s1_b": "ScheduleB",
           "s1_c": "ScheduleC", "s1_d": "ScheduleD"}


def render_s1_subsection(sym, rec, goal) -> str:
    """s1_a/4, s1_b/4, s1_c/4 (Taxp,Taxy,Taxinc,Tax); s1_d/5 adds Spouse in
    second position. Taxable income comes from the injected §63 conclusion."""
    args = goal["args"]
    pred = goal["predicate"]
    taxpayer = args[0]
    year = int(args[2] if pred == "s1_d" else args[1])
    claimed = args[-1]
    ti = (f"(W.injected_money of (W.injections_for_3_12 of injections,"
          f" P.pred_s63_3, {entity_lit(sym, taxpayer)}.id,"
          f" W.num_key of {year}), 3)")
    # `s1_c` reaches its rate schedule through `s63`, which the case may grant
    # *and* the statute derives, so both are consulted (D59).
    tax_scope = (f"(output of S1.Tax with {{ -- world: world"
                 f" -- injections: injections"
                 f" -- taxpayer: {entity_lit(sym, taxpayer)}"
                 f" -- taxable_year: {year} {KIN_ARGS_ALL} }})")
    return (f"(output of S1.SubsectionHolds with {{"
            f" -- status: {status_expr(sym, taxpayer, year)}.status"
            f" -- subsection: S1.Schedule.{_SUBSEC[pred]}"
            f" -- taxable_income: {ti}"
            f" -- derived_income: {tax_scope}.taxable_income"
            f" -- derived_applies: {tax_scope}.taxable_income_applies"
            f" -- claimed_tax: {money_arg(claimed)} }}).holds")


def render_s68_a_2(sym, rec, goal) -> str:
    """s68_a_2(Taxp, Itemded, Reduction, Taxy) -> Section68.ReductionTwoHolds.

    The itemized total comes from the case's `s63_d/4` grant when it made one
    and from the event base otherwise.  Reading a missing grant as `$0` was
    wrong twice over: it ignored deductions the world does hold, and it turned
    SARA's `L>0` failure into a reduction of zero, so an empty world answered
    `s68_a_2(alice,_,0,2016)` true where SARA answers false.
    """
    args = goal["args"]
    taxpayer, claimed, year = args[0], args[2], int(args[3])
    ent = entity_lit(sym, taxpayer)
    matching = (f"(W.injections_for_4_14 of injections, P.pred_s63_d_4,"
                f" {ent}.id, W.num_key of {year})")
    world = (f"(output of S63.ItemizedDeductions with {{ -- world: world"
             f" -- taxpayer: {ent} -- taxable_year: {year} }})")
    itemized = (f"(match (W.injected_money of {matching}, 3) with pattern"
                f" -- Absent: {world}.total -- Present content m: m)")
    itemizes = (f"((W.injected_holds of {matching})"
                f" or {world}.itemizes)")
    return (f"(output of S68.ReductionTwoHolds with {{"
            f" -- itemized: {itemized}"
            f" -- itemizes: {itemizes}"
            f" -- claimed: {money_arg(claimed)} }}).holds")


def render_s68_b(sym, rec, goal) -> str:
    """s68_b(Taxp, Aa, Taxy) -- the applicable amount for the taxpayer's status."""
    taxpayer, claimed, year = goal["args"][0], goal["args"][1], int(goal["args"][2])
    st = status_expr(sym, taxpayer, year)
    return (f"(output of S68.ApplicableAmountHolds with {{"
            f" -- status: S68.status_of_filing of {st}.status"
            f" -- claimed: {money_arg(claimed)} }}).holds")


_S63B = ["Section63 as S63", "Section68 as St", "Section7703 as S7703",
         "Section7703 as P"]
# the two that consult §151(b) derive it as well as reading the grant
_S63B151 = _S63B + ["Section151 as S151"]
for _p in _AGED:
    PORTED[f"{_p}/{2 if _p.endswith('_A') else 3}"] = {
        "render": render_s63_f_clause, "uses": _S63B151}
PORTED["s63_f_3/3"] = {"render": render_s63_f_3, "uses": _S63B}
PORTED["s63_c_3/3"] = {"render": render_s63_c_3, "uses": _S63B151}
PORTED["s63_d/4"] = {"render": render_s63_d, "uses": _S63B}
PORTED["s63_c_6_A/4"] = {"render": render_s63_c_6, "uses": _S63B}
PORTED["s63_c_6_B/2"] = {"render": render_s63_c_6, "uses": _S63B}
PORTED["s63_c_6_D/2"] = {"render": render_s63_c_6, "uses": _S63B}
PORTED["s63_c_5/5"] = {"render": render_s63_c_5, "uses": _S63B}
PORTED["s63_c_2_A_i/3"] = {"render": render_s63_c_2_A, "uses": _S63B}
PORTED["s63_c_2_A_ii/2"] = {"render": render_s63_c_2_A, "uses": _S63B}

_S1B = ["Section1 as S1", "Section68 as St", "Section7703 as P"]
for _p in _SUBSEC:
    PORTED[f"{_p}/{5 if _p == 's1_d' else 4}"] = {
        "render": render_s1_subsection, "uses": _S1B}

_S68B = ["Section68 as S68", "Section68 as St", "Section7703 as S7703",
         "Section7703 as P"]
PORTED["s68_a_2/4"] = {"render": render_s68_a_2,
                       "uses": _S68B + ["Section63 as S63"]}
PORTED["s68_b/3"] = {
    # `s68_b(alice,Aa,2016)` alone, or as the first conjunct of the (a)(1)
    # chain that binds Aa and then uses it.
    "render": (lambda sym, rec, goal:
               render_s68_a_1_conj(sym, rec, goal)
               if len(rec["test"]["goals"]) > 1
               else render_s68_b(sym, rec, goal)),
    "uses": _S68B, "multi": True}





for _l, _ar in (("A", 5), ("B", 3), ("C", 3), ("D", 3)):
    PORTED[f"s68_b_1_{_l}/{_ar}"] = {
        "render": render_s68_subpara, "uses": ["Section68 as S68"]}

# ---------------------------------------------------------------- §3306, §3301

_S3306 = ["Section3306 as S3306"]
KIN4 = KIN_ARGS
KIN7 = (KIN_ARGS + " -- child_in_law_of: child_in_law_of"
        " -- parent_in_law_of: parent_in_law_of"
        " -- sibling_in_law_of: sibling_in_law_of")


def opt_entity(sym, tok: str) -> str:
    """A query argument that Prolog may leave unbound."""
    return "Absent" if is_var(tok) else f"Present content ({entity_lit(sym, tok)})"


def opt_date(tok: str) -> str:
    return "Absent" if is_var(tok) else f"Present content {cat_date(unquote(tok))}"


def opt_year(tok: str) -> str:
    return "Absent" if is_var(tok) else f"Present content {int(tok)}"


def _agri(kin: str = None) -> str:
    """The (a)(2)(B) table every scope that reaches §3306(c) needs."""
    return (" -- agri_employers: (output of S3306.AgriEmployerYears with {"
            " -- world: world -- injections: injections "
            + KIN_ARGS + " -- taxable_year: TAXYEAR }).pairs")


def agri(year: int) -> str:
    return _agri().replace("TAXYEAR", str(year))


def render_s3306_c_6(sym, rec, goal) -> str:
    return (f"(output of S3306.ExclUsGovernment with {{ -- world: world"
            f" -- service: {opt_entity(sym, goal['args'][0])} }}).holds")


def render_s3306_c_7(sym, rec, goal) -> str:
    svc, er = goal["args"]
    return (f"(output of S3306.ExclState with {{ -- world: world"
            f" -- service: {opt_entity(sym, svc)}"
            f" -- employer: {opt_entity(sym, er)} }}).holds")


def render_s3306_c_11(sym, rec, goal) -> str:
    svc, er = goal["args"]
    return (f"(output of S3306.ExclForeignGovernment with {{ -- world: world"
            f" -- service: {opt_entity(sym, svc)}"
            f" -- employer: {opt_entity(sym, er)} }}).holds")


def render_s3306_c_16(sym, rec, goal) -> str:
    svc, er = goal["args"]
    return (f"(output of S3306.ExclInternationalOrganization with {{"
            f" -- world: world -- service: {opt_entity(sym, svc)}"
            f" -- employer: {opt_entity(sym, er)} }}).holds")


def render_s3306_c_21(sym, rec, goal) -> str:
    svc, ee, _s235, day = goal["args"]
    return (f"(output of S3306.ExclPenalInstitution with {{ -- world: world"
            f" -- service: {opt_entity(sym, svc)}"
            f" -- employee: {opt_entity(sym, ee)}"
            f" -- workday: {opt_date(day)} }}).holds")


def render_s3306_c_13(sym, rec, goal) -> str:
    svc, er, ee, day = goal["args"]
    return (f"(output of S3306.ExclStudentNurse with {{ -- world: world"
            f" -- service: {opt_entity(sym, svc)}"
            f" -- employer: {opt_entity(sym, er)}"
            f" -- employee: {opt_entity(sym, ee)}"
            f" -- workday: {opt_date(day)} }}).holds")


def render_s3306_c_5(sym, rec, goal) -> str:
    """s3306_c_5(Service,Employer,Employee,Workday). ExclFamily names its two
    people after the roles they read -- the service's agent and patient --
    because (A) and (B) disagree about which of them has to be the child."""
    svc, er, ee, day = goal["args"]
    return (f"(output of S3306.ExclFamily with {{ -- world: world"
            f" -- child_of: child_of -- service: {opt_entity(sym, svc)}"
            f" -- agent: {opt_entity(sym, ee)}"
            f" -- patient: {opt_entity(sym, er)}"
            f" -- workday: {opt_date(day)} }}).holds")


def render_s3306_c_10_A_i(sym, rec, goal) -> str:
    st, er, day = goal["args"]
    return (f"(output of S3306.Student with {{ -- world: world"
            f" -- student: {opt_entity(sym, st)}"
            f" -- employer: {opt_entity(sym, er)}"
            f" -- workday: {opt_date(day)} }}).holds")


def render_s3306_c_10_A_ii(sym, rec, goal) -> str:
    sp, st, day = goal["args"]
    return (f"(output of S3306.StudentSpouse with {{ -- world: world"
            f" -- injections: injections {KIN4}"
            f" -- spouse: {entity_lit(sym, sp)}"
            f" -- student: {entity_lit(sym, st)}"
            f" -- workday: {opt_date(day)} }}).holds")


def _excl_student(sym, goal, field: str) -> str:
    svc, er, ee, day = goal["args"]
    return (f"(output of S3306.ExclStudent with {{ -- world: world"
            f" -- injections: injections {KIN4}"
            f" -- service: {opt_entity(sym, svc)}"
            f" -- employer: {opt_entity(sym, er)}"
            f" -- employee: {opt_entity(sym, ee)}"
            f" -- workday: {opt_date(day)} }}).{field}")


def render_s3306_c_10_A(sym, rec, goal) -> str:
    return _excl_student(sym, goal, "holds_a")


def render_s3306_c_10_B(sym, rec, goal) -> str:
    return _excl_student(sym, goal, "holds_b")


def render_s3306_c_10(sym, rec, goal) -> str:
    return _excl_student(sym, goal, "holds")


def render_s3306_c_1(sym, rec, goal) -> str:
    svc, caly = goal["args"]
    return (f"(output of S3306.AgriculturalExcluded with {{ -- world: world"
            f" -- service: {opt_entity(sym, svc)}"
            f" -- caly: {opt_year(caly)}"
            f"{agri(int(caly))} }}).holds")


def render_s3306_c_1_B(sym, rec, goal) -> str:
    return (f"(output of S3306.AgriculturalAlien with {{ -- world: world"
            f" -- service: {opt_entity(sym, goal['args'][0])} }}).holds")


def render_s3306_c_1_A_i(sym, rec, goal) -> str:
    """s3306_c_1_A_i(Employer,Remuneration,Employee,Service,Caly). The third
    and fourth arguments are `findall` results -- *lists* -- so a case that
    names a bare atom there can never unify and the goal is false."""
    er, rem, ee, svc, caly = goal["args"]
    call = (f"(output of S3306.AgriculturalWages with {{ -- world: world"
            f" -- employer: {opt_entity(sym, er)}"
            f" -- caly: {int(caly)} }})")
    conds = [f"{call}.holds"]
    if not is_var(ee):
        if ee.startswith("["):
            items = [x for x in ee[1:-1].split(",") if x.strip()]
            lst = "; ".join(entity_lit(sym, x.strip()) for x in items)
            conds.append(f"(({call}.employees) = [{lst}])")
        else:
            return "false"   # an atom can never unify with a findall list
    if not is_var(rem):
        conds.append(f"({call}.total = {money_arg(rem)})")
    return "(" + " and ".join(conds) + ")"


def render_s3306_c_2(sym, rec, goal) -> str:
    svc, _loc, caly = goal["args"]
    return (f"(output of S3306.Excluded with {{ -- world: world"
            f" -- injections: injections {KIN4}"
            f" -- service: {opt_entity(sym, svc)}"
            f" -- employer: Absent -- employee: Absent"
            f" -- workday: Absent }}).domestic_excluded")


def render_s3306_c_A(sym, rec, goal) -> str:
    svc, er, ee = goal["args"]
    return (f"(output of S3306.EmploymentCandidates with {{ -- world: world"
            f" -- service: {opt_entity(sym, svc)}"
            f" -- employer: {opt_entity(sym, er)}"
            f" -- employee: {opt_entity(sym, ee)} }}).holds_a")


def render_s3306_c_B(sym, rec, goal) -> str:
    svc, er, ee, _loc = goal["args"]
    return (f"(output of S3306.EmploymentCandidates with {{ -- world: world"
            f" -- service: {opt_entity(sym, svc)}"
            f" -- employer: {opt_entity(sym, er)}"
            f" -- employee: {opt_entity(sym, ee)} }}).holds_b")


def render_s3306_b_2_A(sym, rec, goal) -> str:
    return (f"(output of S3306.PlanPurpose with {{ -- world: world"
            f" -- plan: {opt_entity(sym, goal['args'][0])} }}).holds_a")


def render_s3306_b_2_C(sym, rec, goal) -> str:
    return (f"(output of S3306.PlanPurpose with {{ -- world: world"
            f" -- plan: {opt_entity(sym, goal['args'][0])} }}).holds_c")


def render_s3306_b_7(sym, rec, goal) -> str:
    rem, svc, er, ee = goal["args"][:4]
    return (f"(output of S3306.ExcludedNonCashOutsideBusiness with {{"
            f" -- world: world -- injections: injections {KIN4}"
            f" -- remuneration: {opt_entity(sym, rem)}"
            f" -- service: {opt_entity(sym, svc)}"
            f" -- employer: {opt_entity(sym, er)}"
            f" -- employee: {opt_entity(sym, ee)} }}).holds")


def render_s3306_b_10_A(sym, rec, goal) -> str:
    rem, emp, ee, er = goal["args"][:4]
    return (f"(output of S3306.ExcludedTerminationPayment with {{"
            f" -- world: world -- remuneration: {opt_entity(sym, rem)}"
            f" -- employment: {opt_entity(sym, emp)}"
            f" -- employee: {opt_entity(sym, ee)}"
            f" -- employer: {opt_entity(sym, er)} }}).holds")


def render_s3306_b_10_B(sym, rec, goal) -> str:
    er, rem, plan = goal["args"]
    return (f"(output of S3306.ExcludedTerminationPlan with {{"
            f" -- world: world -- employer: {opt_entity(sym, er)}"
            f" -- remuneration: {opt_entity(sym, rem)}"
            f" -- plan: {opt_entity(sym, plan)} }}).holds")


def render_s3306_b_11(sym, rec, goal) -> str:
    rem, svc, _m = goal["args"]
    return (f"(output of S3306.ExcludedAgriculturalInKind with {{"
            f" -- world: world -- remuneration: {opt_entity(sym, rem)}"
            f" -- service: {opt_entity(sym, svc)} }}).holds")


def render_s3306_b_15(sym, rec, goal) -> str:
    rem, er, payee, ee, _caly = goal["args"]
    return (f"(output of S3306.ExcludedSurvivorPayment with {{"
            f" -- world: world -- injections: injections {KIN4}"
            f" -- remuneration: {opt_entity(sym, rem)}"
            f" -- employer: {opt_entity(sym, er)}"
            f" -- payee: {opt_entity(sym, payee)}"
            f" -- employee: {opt_entity(sym, ee)} }}).holds")


def _wage_year(rec) -> int:
    """§3306(b) has no year of its own; the (a)(2)(B) table it needs is keyed
    by year, so use any the world mentions -- `AgriEmployerYears` covers them
    all regardless of which is named."""
    return 2000


def render_s3306_b(sym, rec, goal) -> str:
    wages, rem, emp, payer, payee, er, ee, _medium = goal["args"]
    call = (f"(output of S3306.Wages with {{ -- world: world"
            f" -- injections: injections {KIN7}"
            f"{agri(_wage_year(rec))}"
            f" -- remuneration: {opt_entity(sym, rem)}"
            f" -- employment: {opt_entity(sym, emp)}"
            f" -- payer: {opt_entity(sym, payer)}"
            f" -- payee: {opt_entity(sym, payee)}"
            f" -- employer: {opt_entity(sym, er)}"
            f" -- employee: {opt_entity(sym, ee)} }})")
    if is_var(wages):
        return f"{call}.holds"
    return (f"(exists r among {call}.rows such that r.wages = {money_arg(wages)})")


def _employer_wages(sym, er, caly) -> str:
    return (f"(output of S3306.EmployerWages with {{ -- world: world"
            f" -- injections: injections {KIN7}"
            f"{agri(caly)}"
            f" -- person: {entity_lit(sym, er)} -- caly: {caly} }})")


def render_s3306_a_1_A(sym, rec, goal) -> str:
    er, caly, wages = goal["args"]
    call = _employer_wages(sym, er, int(caly))
    if is_var(wages):
        return f"{call}.holds_1_A"
    return f"({call}.holds_1_A and {call}.general_total = {money_arg(wages)})"


def render_s3306_a_2_A(sym, rec, goal) -> str:
    er, caly, wages, _svc = goal["args"]
    call = _employer_wages(sym, er, int(caly))
    if is_var(wages):
        return f"{call}.holds_2_A"
    return f"({call}.holds_2_A and {call}.agri_total = {money_arg(wages)})"


def render_s3306_a_3(sym, rec, goal) -> str:
    er, _svc, wages, caly = goal["args"]
    call = _employer_wages(sym, er, int(caly))
    if is_var(wages):
        return f"{call}.holds_3"
    return f"({call}.holds_3 and {call}.domestic_total = {money_arg(wages)})"


def _employer_days(sym, er, caly) -> str:
    return (f"(output of S3306.EmployerDays with {{ -- world: world"
            f" -- injections: injections {KIN4}"
            f" -- employer: {entity_lit(sym, er)} -- caly: {caly} }})")


def render_s3306_a_1_B(sym, rec, goal) -> str:
    er, _days, _ees, caly = goal["args"]
    return f"{_employer_days(sym, er, int(caly))}.holds_general"


def render_s3306_a_2_B(sym, rec, goal) -> str:
    er = goal["args"][0]
    caly = int(goal["args"][-1])
    return f"{_employer_days(sym, er, caly)}.holds_agricultural"


def _employer(sym, er, caly) -> str:
    return (f"(output of S3306.Employer with {{ -- world: world"
            f" -- injections: injections {KIN7}"
            f"{agri(caly)}"
            f" -- person: {entity_lit(sym, er)} -- caly: {caly} }})")


def render_s3306_a_1(sym, rec, goal) -> str:
    er, caly = goal["args"]
    return f"{_employer(sym, er, int(caly))}.holds_1"


def render_s3306_a_2(sym, rec, goal) -> str:
    er, caly = goal["args"]
    return f"{_employer(sym, er, int(caly))}.holds_2"


def render_s3306_a(sym, rec, goal) -> str:
    er, caly = goal["args"]
    return f"{_employer(sym, er, int(caly))}.holds"


def render_s3301(sym, rec, goal) -> str:
    """s3301(Employer,Caly,Wages,Employee,Employment,Tax)."""
    er, caly, wages, _ees, _emp, tax = goal["args"]
    call = (f"(output of S3306.UnemploymentTax with {{ -- world: world"
            f" -- injections: injections {KIN7}"
            f" -- employer: {entity_lit(sym, er)} -- caly: {int(caly)} }})")
    conds = [f"{call}.holds"]
    if not is_var(tax):
        conds.append(f"{call}.tax = {money_arg(tax)}")
    if not is_var(wages):
        conds.append(f"{call}.wages = {money_arg(wages)}")
    return "(" + " and ".join(conds) + ")"


PORTED["s3306_c_6/1"] = {"render": render_s3306_c_6, "uses": _S3306}
PORTED["s3306_c_7/2"] = {"render": render_s3306_c_7, "uses": _S3306}
PORTED["s3306_c_11/2"] = {"render": render_s3306_c_11, "uses": _S3306}
PORTED["s3306_c_16/2"] = {"render": render_s3306_c_16, "uses": _S3306}
PORTED["s3306_c_21/4"] = {"render": render_s3306_c_21, "uses": _S3306}
PORTED["s3306_c_13/4"] = {"render": render_s3306_c_13, "uses": _S3306}
PORTED["s3306_c_5/4"] = {"render": render_s3306_c_5, "uses": _S3306}
PORTED["s3306_c_10_A_i/3"] = {"render": render_s3306_c_10_A_i, "uses": _S3306}
PORTED["s3306_c_10_A_ii/3"] = {"render": render_s3306_c_10_A_ii, "uses": _S3306}
PORTED["s3306_c_10_A/4"] = {"render": render_s3306_c_10_A, "uses": _S3306,
                            "multi": True}
PORTED["s3306_c_10_B/4"] = {"render": render_s3306_c_10_B, "uses": _S3306}
PORTED["s3306_c_10/4"] = {"render": render_s3306_c_10, "uses": _S3306}
PORTED["s3306_c_1/2"] = {"render": render_s3306_c_1, "uses": _S3306}
PORTED["s3306_c_1_B/2"] = {"render": render_s3306_c_1_B, "uses": _S3306}
PORTED["s3306_c_1_A_i/5"] = {"render": render_s3306_c_1_A_i, "uses": _S3306}
PORTED["s3306_c_2/3"] = {"render": render_s3306_c_2, "uses": _S3306}
PORTED["s3306_c_A/3"] = {"render": render_s3306_c_A, "uses": _S3306}
PORTED["s3306_c_B/4"] = {"render": render_s3306_c_B, "uses": _S3306}
PORTED["s3306_b_2_A/1"] = {"render": render_s3306_b_2_A, "uses": _S3306}
PORTED["s3306_b_2_C/1"] = {"render": render_s3306_b_2_C, "uses": _S3306}
PORTED["s3306_b_7/6"] = {"render": render_s3306_b_7, "uses": _S3306}
PORTED["s3306_b_10_A/6"] = {"render": render_s3306_b_10_A, "uses": _S3306}
PORTED["s3306_b_10_B/3"] = {"render": render_s3306_b_10_B, "uses": _S3306}
PORTED["s3306_b_11/3"] = {"render": render_s3306_b_11, "uses": _S3306}
PORTED["s3306_b_15/5"] = {"render": render_s3306_b_15, "uses": _S3306}
PORTED["s3306_b/8"] = {"render": render_s3306_b, "uses": _S3306}
PORTED["s3306_a_1_A/3"] = {"render": render_s3306_a_1_A, "uses": _S3306}
PORTED["s3306_a_2_A/4"] = {"render": render_s3306_a_2_A, "uses": _S3306}
PORTED["s3306_a_3/4"] = {"render": render_s3306_a_3, "uses": _S3306}
PORTED["s3306_a_1_B/4"] = {"render": render_s3306_a_1_B, "uses": _S3306}
PORTED["s3306_a_2_B/6"] = {"render": render_s3306_a_2_B, "uses": _S3306}
PORTED["s3306_a_1/2"] = {"render": render_s3306_a_1, "uses": _S3306}
PORTED["s3306_a_2/2"] = {"render": render_s3306_a_2, "uses": _S3306}
PORTED["s3306_a/2"] = {"render": render_s3306_a, "uses": _S3306}
PORTED["s3301/6"] = {"render": render_s3301, "uses": _S3306}


def render_tax(sym, rec, goal) -> str:
    """tax(Taxp,Taxy,Tax) -- §1 plus §3301, against the case's gold figure."""
    taxpayer, year, claimed = goal["args"]
    return (f"((output of S1.Total with {{ -- world: world"
            f" -- injections: injections -- taxpayer: {entity_lit(sym, taxpayer)}"
            f" -- taxable_year: {int(year)} {KIN_ARGS_ALL} }}).total"
            f" = {money_arg(claimed)})")


PORTED["tax/3"] = {"render": render_tax, "uses": ["Section1 as S1"]}




class Symbols:
    """One integer key space over atoms, dates and numbers, stable across cases.

    New ids come from `max + 1` rather than `len + 1` so that a table *seeded*
    with part of an earlier key space --- the predicate keys recovered from
    `Section7703.catala_en`, whose values the compiled port depends on ---
    cannot hand a fresh atom an id one of them already holds.  Built from
    empty the two rules agree, since ids are then handed out 1, 2, 3, ...
    """

    def __init__(self) -> None:
        self.table: dict[str, int] = {}

    def key(self, kind: str, value) -> int:
        k = f"{kind}:{value}"
        if k not in self.table:
            self.table[k] = max(self.table.values(), default=0) + 1
        return self.table[k]

    def entity(self, atom: str) -> int:
        return self.key("e", atom)


ENTITY_TAGS = {
    "decree of divorce": "DecreeOfDivorce",
    "decree of separate maintenance": "DecreeOfSeparateMaintenance",
    "usa": "UsaEntity",
}


def entity_tag(atom: str, kind: str = "str") -> str:
    """The Section7703.EntityTag for one interned atom or string.

    Which tags a value earns depends on how SARA tests for it, and the two
    kinds of test do not agree.  `Employer=="united states government"` and
    `Geographical_location=="usa"` are *equality* against a string literal, and
    SWI's `==` tells an atom from a string, so `location_(e,usa)` is not a
    location in the USA and `s3306_c_A` fails on it.  `atom_prefix/2` and
    `sub_atom/5` convert their argument, so the state and foreign-government
    prefixes apply to either kind.  See D68.
    """
    if atom.startswith("state of "):
        return "StateEntity"          # mirrors atom_prefix/2 in §3306(c)(7)
    if atom.endswith(" government") and atom != "united states government":
        return "ForeignGovernmentEntity"        # sub_atom/5 in §3306(c)(11)
    if kind != "str":
        return "PlainEntity"
    if atom == "united states government":
        return "UnitedStatesGovernmentEntity"   # §3306(c)(6)
    return ENTITY_TAGS.get(atom, "PlainEntity")


def cat_date(s: str) -> str:
    return "|" + s + "|"


def unquote(tok: str) -> str:
    """A query argument may be a quoted Prolog string -- `s63_c_6_D("Walter
    Brown Family Trust II",1999)`. The grounded facts hold the atom without its
    quotes, so both must intern to the same symbol.

    Whitespace *around the quotes* is punctuation and goes; whitespace inside
    the value is part of it and stays. `"state of "` is the case that makes the
    difference -- it is §3306(c)(7)'s prefix, trailing space and all -- and
    trimming it interned the quoted query argument and the bare fact value as
    two different entities, one tagged `StateEntity` and one `PlainEntity`.
    """
    tok = tok.strip()
    if len(tok) >= 2 and tok[0] == tok[-1] and tok[0] in "\"'":
        return tok[1:-1]
    return tok


def entity_lit(sym: Symbols, atom: str, kind: str | None = None) -> str:
    """One Prolog term as a `W.Entity`.

    Atoms and strings live in separate key spaces, because SWI's `==` tells
    them apart and SARA relies on that: `location_(e,usa)` does not satisfy
    §3306(c)(A)'s `location_(Service,"usa")`, and `purpose_(p,alice_employer)`
    names a service event where `purpose_(p,"alice_employer")` names nothing.
    Folding the two into one id made the port answer questions the statutes
    would have refused; the fuzzer found it in a three-fact world.

    `kind` is passed where the caller knows it (a fact's value, typed from the
    sources by `saralib.value_types`).  Where it is not -- a query
    argument, which arrives as raw Prolog text -- the quoting decides.
    """
    # Strip only raw Prolog text, where the whitespace is punctuation.  A typed
    # value is exact: §3306(c)(7)'s prefix `"state of "` needs its trailing space.
    raw = atom
    if kind is None:
        raw = atom.strip()
        kind = "str" if raw[:1] == '"' else "atom"
        atom = unquote(raw)
    else:
        # From the fact base rather than Prolog source: no punctuation to trim.
        atom = raw[1:-1] if (len(raw) >= 2 and raw[0] == raw[-1]
                             and raw[0] in "\"'") else raw
    space = "s" if kind == "str" else "e"
    return (f"W.Entity {{ -- id: {sym.key(space, atom)}"
            f" -- tag: W.EntityTag.{entity_tag(atom, kind)} }}")


def classify_value(sym: Symbols, pred: str, value, kind: str = "atom"):
    """Render one role value into the Catala constructor its field expects.

    `kind` is the value's Prolog syntax, "atom" or "str".  The closed
    vocabularies are matched only against strings, since that is how SARA
    writes every one of them.
    """
    field = ROLE_FIELDS[pred]
    if field in ("starts", "ends"):
        return cat_date(value) if DATE_RE.match(str(value)) else None
    if field == "amounts":
        return f"(money of {int(value)})" if isinstance(value, int) else None
    if field in ("purposes", "types"):
        # type_/2 shares purpose_/2's vocabulary: §3306(c)(1) tests both against
        # "agricultural labor", and §3306(b)(7) compares two type_ values.
        if kind == "str" and value in PURPOSES:
            return f"W.Purpose.{PURPOSES[value]}"
        return f"W.Purpose.PurposeEntity content ({entity_lit(sym, str(value), kind)})"
    if field in ("places", "destinations"):
        if kind == "str" and value in PLACES:
            return f"W.Place.{PLACES[value]}"
        return f"W.Place.NamedPlace content ({entity_lit(sym, str(value), kind)})"
    if field == "media":
        if kind == "str" and value in MEDIA:
            return f"W.Medium.{MEDIA[value]}"
        return f"W.Medium.MediumEntity content ({entity_lit(sym, str(value), kind)})"
    return entity_lit(sym, str(value), kind)


def build_events(sym: Symbols, events: dict,
                 types: dict | None = None) -> tuple[dict[str, list[str]], list[str]]:
    """Group the flat fact base into one list per unary event predicate.

    An event identifier may satisfy several unary predicates. Its relevant
    fields are emitted into every corresponding category. Roles not carried by
    any such category become narrow binary facts; there is no universal event
    record, canonical-copy flag, or universal role table.

    `types` is the atom/string table from `saralib.value_types`.  It has
    to reach `classify_value`, because the closed vocabularies match only
    strings: without it every `purpose_(e,"agricultural labor")` renders as a
    `PurposeEntity` naming an atom of that spelling, which no statute test can
    ever satisfy.
    """
    from .value_types import kind_of, table_for
    if types is None:
        types = table_for()
    # Keyed by (identifier, atom-or-string): the subject of a fact is typed
    # like any other argument, and the two readings are different SWI terms.
    # `location_(e,"baltimore, ...")` and `country_("baltimore, ...","usa")`
    # name the same place only because both subjects are strings.
    per_event: dict[tuple, dict[str, list[str]]] = {}
    universal_purposes: list[str] = []

    def slot(key: tuple) -> dict[str, list[str]]:
        return per_event.setdefault(key, {})

    for pred, kind in EVENT_KINDS.items():
        for row in events.get(pred, []):
            eid = str(row[0])
            if VAR_RE.match(eid):
                continue
            slot((eid, kind_of(types, pred, 0, eid))).setdefault(
                "categories", []).append(kind)

    for pred, field in ROLE_FIELDS.items():
        for row in events.get(pred, []):
            if len(row) != 2:
                continue
            eid, value = str(row[0]), row[1]
            if VAR_RE.match(str(value)):
                continue
            rendered = classify_value(sym, pred, value,
                                      kind_of(types, pred, 1, value))
            if rendered is None:
                continue
            if VAR_RE.match(eid):
                # A universally quantified fact: purpose_(_, "agricultural labor").
                if field == "purposes":
                    universal_purposes.append(rendered)
                continue
            slot((eid, kind_of(types, pred, 0, eid))).setdefault(
                field, []).append(rendered)

    fields = ["agents", "patients", "starts", "ends", "amounts",
              "purposes", "places", "media", "reasons", "beneficiaries",
              "countries", "types", "destinations"]
    literals = {field: [] for field in EVENT_FIELDS.values()}
    literals.update({field: [] for _, field in ROLE_FACTS.values()})
    for eid, ekind in sorted(per_event):
        event = per_event[(eid, ekind)]
        categories = event.get("categories", [])
        target_specs = [
            (EVENT_FIELDS[pred], pred)
            for pred, constructor in EVENT_KINDS.items()
            if constructor in categories
        ]
        for target, pred in target_specs:
            kept_fields = EVENT_CATEGORY_ROLES[pred]
            if pred == "income_":
                # Each row is one solution of SARA's conjunction
                # income_/agent_/start_/amount_. Missing roles contribute no
                # solution; repeated role facts retain their Cartesian
                # multiplicity without nested symbolic lists.
                for agent, start, amount in itertools.product(
                        event.get("agents", []), event.get("starts", []),
                        event.get("amounts", [])):
                    amount_match = re.fullmatch(r"\(money of (-?\d+)\)", amount)
                    if amount_match is None:
                        raise ValueError(f"invalid rendered income amount: {amount}")
                    literals[target].append(
                        "W.IncomeEvent {"
                        f" -- agent: {agent}"
                        f" -- start: {start}"
                        f" -- amount: {amount} }}"
                    )
                continue
            if pred == "deduction_":
                # Preserve the two observably different dated states:
                # §63(c)(6)(A) accepts a dated claim without an amount, while
                # §63(d) requires both. Amounts without dates cannot satisfy
                # either rule and are therefore observationally undated.
                starts = event.get("starts", [])
                amounts = event.get("amounts", [])
                for role, vals in (("starts", starts), ("amounts", amounts)):
                    if len(vals) > 1:
                        raise EventCardinalityError(
                            f"{pred} event {eid!r} has {len(vals)} values for "
                            f"0-or-1 role {role!r}")
                if not starts:
                    evidence = "W.DeductionEvidence.Undated"
                elif not amounts:
                    evidence = (
                        "W.DeductionEvidence.DatedClaim content "
                        f"({starts[0]})")
                else:
                    evidence = (
                        "W.DeductionEvidence.DatedAmount content "
                        "(W.DeductionOccurrence {"
                        f" -- start: {starts[0]}"
                        f" -- amount: {amounts[0]} }})")
                literals[target].append(
                    "W.DeductionEvent {\n"
                    f"        -- agents: [{'; '.join(event.get('agents', []))}]\n"
                    f"        -- evidence: {evidence} }}"
                )
                continue
            rendered_fields = {}
            for f in kept_fields:
                vals = event.get(f, [])
                if (pred, f) in OPTIONAL_CATEGORY_ROLES:
                    if len(vals) > 1:
                        raise EventCardinalityError(
                            f"{pred} event {eid!r} has {len(vals)} values for "
                            f"0-or-1 role {f!r}")
                    rendered_fields[f] = (
                        "Absent" if not vals
                        else f"Present content ({vals[0]})")
                else:
                    rendered_fields[f] = f"[{'; '.join(vals)}]"
            parts = [
                f"-- ident: {entity_lit(sym, eid, ekind)}",
                *(f"-- {f}: {rendered_fields[f]}" for f in kept_fields),
            ]
            structure = f"{EVENT_KINDS[pred]}Event"
            literals[target].append(
                f"W.{structure} {{\n        " + "\n        ".join(parts) + " }"
            )
        covered_roles = {
            role for _, pred in target_specs for role in EVENT_CATEGORY_ROLES[pred]
        }
        subject = entity_lit(sym, eid, ekind)
        for role in fields:
            if role in covered_roles:
                continue
            constructor, target = ROLE_FACTS[role]
            for value in event.get(role, []):
                literals[target].append(
                    f"W.{constructor} {{ -- subject: {subject} -- value: {value} }}"
                )
    return literals, universal_purposes


def injection_key_value(sym: Symbols, value) -> tuple[int, str | None]:
    """Encode one injection argument exactly as the Catala matcher reads it.

    The former five-constructor value at every tuple position was immediately
    collapsed to this tagged integer by `injection_key`.  Dates retain their
    concrete literal only for the few positions that callers project back.
    """
    if isinstance(value, str) and VAR_RE.match(value):
        return -1, None
    if isinstance(value, list) or isinstance(value, bool):
        return -2, None
    if isinstance(value, int):
        return 1_000_000 + value, None
    if isinstance(value, str) and DATE_RE.match(value):
        return 2_000_000 + date.fromisoformat(value).toordinal(), value
    raw = str(value).strip()
    kind = "str" if raw[:1] == '"' else "atom"
    atom = unquote(raw)
    return sym.key("s" if kind == "str" else "e", atom), None


_DISCONT_CACHE: dict | None = None


def _discontiguous_table() -> dict:
    """case id -> the `discontiguous` declarations its Prolog file makes.

    Built by `saralib.prolog`, which imports this module, so it is read from
    its JSON rather than imported back.
    """
    global _DISCONT_CACHE
    if _DISCONT_CACHE is None:
        from .paths import DISCONTIGUOUS as path
        _DISCONT_CACHE = json.loads(path.read_text()) if path.exists() else {}
    return _DISCONT_CACHE


def build_injections(sym: Symbols, other: dict,
                     discontiguous=()) -> list[str]:
    """The case's real injected conclusions, including override semantics.

    Injecting a statute conclusion without declaring the predicate
    `discontiguous` replaces the statute's clauses instead of appending to
    them.  This is decisive because the clause being replaced can be the one
    that made a guard vacuous. No synthetic marker rows are emitted.
    """
    out = []
    declared = set(discontiguous)
    for pred, rows in sorted(other.items()):
        if not re.match(r"^s\d", pred) and pred.split("/")[0] not in INJECTABLE_UTILS:
            continue  # case-local helper, not a statute conclusion
        pkey = sym.key("p", pred)
        replaces = "true" if pred not in declared else "false"
        for row in rows:
            if not 1 <= len(row) <= 8:
                raise ValueError(f"unsupported injection arity {len(row)} for {pred}")
            names = ("one", "two", "three", "four", "five", "six", "seven", "eight")
            ignored = IGNORED_INJECTION_POSITIONS.get(pred, set())
            encoded = [(-2, None) if i in ignored
                       else injection_key_value(sym, value)
                       for i, value in enumerate(row)]
            rendered = [f"-- {names[i]}: {key}"
                        for i, (key, _date) in enumerate(encoded)]
            date_positions = {
                4: ((2, "three_date"), (3, "four_date")),
                5: ((3, "four_date"),),
                6: ((4, "five_date"), (5, "six_date")),
            }.get(len(row), ())
            rendered.extend(
                f"-- {field}: "
                + (f"Present content ({cat_date(encoded[i][1])})"
                   if encoded[i][1] is not None else "Absent")
                for i, field in date_positions
            )
            out.append(
                f"W.Injection {{ -- pred: {pkey}"
                f" -- replaces_statute: {replaces}"
                f" -- arguments: W.InjectionArguments.Args{len(row)} content"
                f" (W.InjectionArgs{len(row)} {{ {' '.join(rendered)} }}) }}"
            )
    return out


def emit_case(sym: Symbols, rec: dict, standalone: bool = False,
              provenance: str = "") -> str:
    """The world model and its query as one Catala program.

    With `standalone` the program declares no module of its own, so it can sit
    anywhere on disk under any file name and be run directly:

        catala interpret catala.catala_en -s Run -I data/catala_gold/sara \\
            --stdlib data/catala_gold/sara/_build/libcatala --bin data/catala_gold/sara/_build

    Without it, the program is the importable module `Case_<id>` and has to be
    named for it, which is how the port's own `data/catala_gold/sara/cases/` are built.
    """
    from .value_types import table_for
    # A fuzz mutant carries its own overrides for the six values SARA quotes
    # inconsistently; a real case is looked up by id.
    types = {**table_for(rec["id"]), **rec.get("value_kinds", {})}
    events_by_field, universal = build_events(sym, rec["events"], types)
    # A fuzz record carries its own declarations, an empty list included; a
    # corpus record has no such field, which is not "nothing declared".
    disc = rec.get("discontiguous")
    if disc is None:
        disc = _discontiguous_table().get(rec["id"], ())
    injections = build_injections(sym, rec["other"], disc)
    module = "Case_" + rec["id"]
    test = rec["test"]

    goal = test["goals"][0]
    ported = PORTED.get(f"{goal['predicate']}/{len(goal['args'])}")
    if ported is not None and len(test["goals"]) > 1 and not ported.get("multi"):
        # Six cases state a conjunction whose conjuncts share variables, so
        # dispatching on the first goal alone answers the wrong question: a
        # renderer must opt in with "multi" to see them.
        ported = None
    uses = ""
    if ported:
        query = ported["render"](sym, rec, goal)
        uses = "".join(f"\n> Using {u}" for u in ported.get("uses", []))
        unported = ""
    else:
        query = "false"
        why = ("is a multi-goal conjunction, not yet handled"
               if len(test["goals"]) > 1 else "has no Catala section yet")
        unported = (
            f"\n## UNPORTED: {goal['predicate']}/{len(goal['args'])} {why}; "
            "`verdict` is a placeholder.\n")

    world_fields = []
    for field in EVENT_FIELDS.values():
        values = events_by_field[field]
        if field in OPTIONAL_EVENT_FIELDS:
            if len(values) > 1:
                raise EventCardinalityError(
                    f"world has {len(values)} events for 0-or-1 category "
                    f"{field!r}")
            rendered = "Absent" if not values else f"Present content ({values[0]})"
            world_fields.append(f"-- {field}: {rendered}")
        else:
            rendered = ";\n      ".join(values)
            world_fields.append(f"-- {field}: [\n      {rendered}\n    ]")
    for _, field in ROLE_FACTS.values():
        rendered = ";\n      ".join(events_by_field[field])
        world_fields.append(f"-- {field}: [\n      {rendered}\n    ]")
    modline = "" if standalone else f"\n> Module {module}\n"
    prov = provenance or (
        f"Generated from `.port/sara/build/cases_grounded/{rec['id']}.json` by\n"
        f"`prolog_to_catala/sara/generate_test_cases.py`. Do not edit.")
    question = f"\nQuestion: {rec['question']}\n" if rec.get("question") else ""
    return f"""# Case {rec['id']}
{modline}
> Using Section7703 as W
> Using Section7703 as K{uses}

{prov}
{question}
Prolog test goal: `{test['raw']}`
{unported}
```catala-metadata
declaration scope Run:
  output world content W.World
  output injections content list of W.Injection
  output child_of content list of K.Kinship
  output sibling_of content list of K.Kinship
  output descendent_of content list of K.Kinship
  output stepsibling_of content list of K.Kinship
  output stepparent_of content list of K.Kinship
  output child_in_law_of content list of K.Kinship
  output parent_in_law_of content list of K.Kinship
  output sibling_in_law_of content list of K.Kinship
  output verdict content boolean
```

```catala
scope Run:
  definition world equals W.World {{
    {chr(10).join(world_fields)}
    -- universal_purposes: [{'; '.join(universal)}]
  }}

  definition injections equals [
    {(';' + chr(10) + '    ').join(injections)}
  ]

  definition child_of equals
    (output of K.Kinships with {{ -- world: world }}).child_of
  definition sibling_of equals
    (output of K.Kinships with {{ -- world: world }}).sibling_of
  definition descendent_of equals
    (output of K.Kinships with {{ -- world: world }}).descendent_of
  definition stepsibling_of equals
    (output of K.InLaws with {{
       -- world: world -- child_of: child_of
       -- sibling_of: sibling_of }}).stepsibling_of
  definition stepparent_of equals
    (output of K.InLaws with {{
       -- world: world -- child_of: child_of
       -- sibling_of: sibling_of }}).stepparent_of
  definition child_in_law_of equals
    (output of K.InLaws with {{
       -- world: world -- child_of: child_of
       -- sibling_of: sibling_of }}).child_in_law_of
  definition parent_in_law_of equals
    (output of K.InLaws with {{
       -- world: world -- child_of: child_of
       -- sibling_of: sibling_of }}).parent_in_law_of
  definition sibling_in_law_of equals
    (output of K.InLaws with {{
       -- world: world -- child_of: child_of
       -- sibling_of: sibling_of }}).sibling_in_law_of

  definition verdict equals {query}
```
"""


def write_predicates_module(sym: Symbols) -> int:
    """Refresh the predicate constants embedded in `Section7703.catala_en`.

    Predicate keys are interned integers; the Layer-1 modules refer to them by
    name (`P.pred_s7703_4`) rather than by magic number.  The key space is
    frozen in `.port/sara/build/symbols.json` precisely so those names keep
    meaning the same thing --- rewriting this module is only correct when that
    file is rebuilt and the whole port recompiled with it.
    """
    preds = sorted((k[2:], v) for k, v in sym.table.items() if k.startswith("p:"))
    lines = []
    for name, key in preds:
        ident = "pred_" + name.replace("/", "_")
        lines.append(f"declaration {ident} content integer equals {key}")
    path = CATALA_PROJECT / "Section7703.catala_en"
    text = path.read_text()
    pattern = r"(?:^declaration pred_[^\n]+\n)+"
    replacement = "\n".join(lines) + "\n"
    text, count = re.subn(pattern, replacement, text, count=1, flags=re.M)
    if count != 1:
        raise RuntimeError(f"predicate declaration block not found in {path}")
    path.write_text(text)
    return len(preds)
