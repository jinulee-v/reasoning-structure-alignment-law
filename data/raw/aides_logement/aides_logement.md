# Tâches requises

Formalisez les textes fournis afin qu'un appelant puisse :

- `AL-ELIGIBILITE-AIDE`: déterminer l'éligibilité à l'aide au logement ;
- `AL-MONTANT-AIDE`: calculer le montant de l'aide au logement applicable à un
  ménage concret ;
- `AL-TRAITEMENT-IMPAYES`: déterminer le traitement applicable aux impayés de
  logement ;
- `AL-MONTANT-IMPAYES`: calculer le montant résultant du traitement des
  impayés ;
- `AL-ELIGIBILITE-DEMENAGEMENT`: déterminer l'éligibilité à la prime de
  déménagement ;
- `AL-MONTANT-DEMENAGEMENT`: calculer le montant de la prime de déménagement ;
  et
- `AL-AGE-RETRAITE`: déterminer l'âge d'ouverture des droits à la retraite
  utilisé par les règles d'aide au logement.

Exposez des champs d'application appelables par machine. Vous pouvez choisir
librement les noms, structures de données et décompositions internes. Les
entrées doivent décrire les faits du cas et non le montant ou la conclusion
juridique que les textes doivent calculer.

Chaque identifiant d'exigence ci-dessus doit avoir une entrée correspondante
dans `REQUIREMENT_OUTPUTS.json`, indiquant le fichier source Catala, un champ
d'application appelable par machine dans ce fichier et une variable de sortie
de premier niveau qui fournit le résultat.

For input values that have realistic default values, please include their
default values in the code.

## Description des variables d'entrée

Après validation des champs d'application Catala, exécutez
`/rtdf/extract_input_requirements.sh`. Cet outil appelle `clerk json-schema` pour
chaque paire fichier-champ d'application distincte choisie dans
`REQUIREMENT_OUTPUTS.json`, puis écrit une seule description globale pour chaque
entrée unique des catégories `fields`, `enums` et `structs` dans
`INPUT_VARIABLE_DESCRIPTION.json`. L'évaluateur déduit les clés pertinentes du
champ d'application choisi. Chaque champ indique les identifiants `FICHIER::CHAMP`
qui le demandent. Les entrées partagées n'apparaissent qu'une seule fois.
Renseignez chaque description en précisant la personne ou
l'entité, la période, l'unité, le sens des relations, l'agrégation, les inclusions
et exclusions et la signification des valeurs par défaut. Relancez l'outil
après toute modification des entrées. Aucune description ne doit rester vide.
