"""Names and row types of the list-based public SARA World."""
WORLD_FAMILIES = {
    'dependency': ('dependency_candidates', 'Entity'),
    'financial': ('financial_facts', 'FinancialFact'),
    'relationship': ('relationship_facts', 'RelationshipFact'),
    'employment': ('employment_facts', 'EmploymentFact'),
    'status': ('status_facts', 'StatusFact'),
}
WORLD_LIST_TYPES = dict(WORLD_FAMILIES.values())
NO_FACTS = frozenset({'NoFinancialFact', 'NoRelationshipFact', 'NoEmploymentFact', 'NoStatusFact'})
