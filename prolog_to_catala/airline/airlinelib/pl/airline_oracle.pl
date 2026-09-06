% The airline checked-bag policy, as one shared Prolog formalization.
%
% DeonticBench ships no shared statute: each of its 300 airline cases carries a
% self-contained program with the rules and the facts together.  This file is
% the missing piece --- the same statute, once, over a world given as facts ---
% and it plays the role SARA's statutes/prolog/ plays: the differential oracle
% the Catala port is measured against, and the only thing a fuzzed world can be
% run on, since a per-case program's facts are baked into it.
%
% It is itself validated, against all 300 per-case programs on their own
% worlds.  See prolog_to_catala/airline/README.md.
%
% A world is:
%     origin(City).  destination(City).  cabin(Cabin).  ticket(Dollars).
%     item(Id, Kind, Length, Width, Height, Weight).   % inches x3, lbs
% Items are positioned in Id order.  `Kind` is one of ordinary_bag,
% soft_sided_garment_bag, diaper_bag, breast_pump, breast_milk_cooler,
% child_safety_seat, stroller, medical_or_mobility_device.
% Optionally the world may also state, for the Complimentary Bags section:
%     status_at_ticketing(S). status_at_checkin(S).   % no_status | gold |
%                                                     % platinum | platinum_pro
%                                                     % | executive_platinum
%     cardmember.  military(M).  flagship.  children(N).

:- discontiguous country/2.

% A world with no items at all leaves `item/5` with no clauses, and calling an
% undefined predicate is an existence_error in SWI rather than a failure --- so
% the empty world threw where every other world computed.  Declaring the world
% predicates dynamic makes "no such fact" mean false, which is what the
% enumerator gets for free by asserting into them and what a standalone
% prolog.pl has to be told.
:- dynamic origin/1, destination/1, cabin/1, ticket/1, item/6.
% The Complimentary Bags section turns on passenger attributes no case can
% state; they default to nothing when the world does not mention them.
:- dynamic status_at_ticketing/1, status_at_checkin/1, cardmember/0,
           military/1, flagship/0, children/1.
% Defaults, so that a standalone `prolog.pl` that mentions none of these still
% runs.  The enumerator retracts them before asserting a world's own, so they
% cannot shadow it.
status_at_ticketing(no_status). status_at_checkin(no_status).
military(not_military). children(0).

% ---------------------------------------------------------------- gazetteer
country(atlanta,us). country(austin,us). country(boston,us). country(charlotte,us).
country(chicago,us). country(dallas,us). country(denver,us). country(houston,us).
country(las_vegas,us). country(los_angeles,us). country(miami,us).
country(minneapolis,us). country(new_orleans,us). country(new_york,us).
country(orlando,us). country(philadelphia,us). country(phoenix,us).
country(portland,us). country(sacramento,us). country(salt_lake_city,us).
country(san_francisco,us). country(seattle,us). country(washington_dc,us).
country(san_juan,puerto_rico). country(charlotte_amalie,us_virgin_islands).
country(tegucigalpa,honduras).
country(georgetown,guyana). country(paramaribo,suriname).
country(montreal,canada). country(ottawa,canada). country(toronto,canada).
country(vancouver,canada).
country(mexico_city,mexico).
country(havana,cuba).
country(port_au_prince,haiti).
country(panama_city,panama).
country(bogota,colombia). country(lima,peru). country(quito,ecuador).
country(buenos_aires,argentina). country(rio_de_janeiro,brazil).
country(amsterdam,europe). country(athens,europe). country(barcelona,europe).
country(berlin,europe). country(brussels,europe). country(helsinki,europe).
country(london,europe). country(madrid,europe). country(munich,europe).
country(paris,europe). country(roma,europe). country(stockholm,europe).
country(vienna,europe). country(zurich,europe).
country(jerusalem,israel). country(doha,qatar).
country(beijing,china). country(chengdu,china). country(guangzhou,china).
country(shanghai,china). country(shenzhen,china). country(wuhan,china).
country(xiamen,china).
country(hong_kong,hong_kong).
country(kyoto,japan). country(nagoya,japan). country(osaka,japan).
country(tokyo,japan).
country(busan,south_korea). country(incheon,south_korea). country(seoul,south_korea).
country(mumbai,india). country(new_delhi,india).
country(melbourne,australia). country(sydney,australia). country(auckland,new_zealand).

origin_country(C)      :- origin(X), country(X,C).
destination_country(C) :- destination(X), country(X,C).

% "Between X and Y", symmetric.
touches(Set)  :- origin_country(A), destination_country(B),
                 ( memberchk(A,Set) ; memberchk(B,Set) ), !.
% "Within and between ...", both endpoints inside.
within(Set)   :- origin_country(A), destination_country(B),
                 memberchk(A,Set), memberchk(B,Set).

us_pr([us,puerto_rico,us_virgin_islands]).
us_pr_canada([us,puerto_rico,us_virgin_islands,canada]).
guyana_suriname([guyana,suriname]).
andean([colombia,ecuador,peru]).
other_south_america([argentina,brazil]).
south_america([colombia,ecuador,peru,argentina,brazil]).
europe_israel_qatar([europe,israel,qatar]).
asia([india,china,japan,south_korea,hong_kong]).
australasia([australia,new_zealand]).
long_haul_pacific([india,china,japan,south_korea,hong_kong,australia,new_zealand]).

to_cuba   :- destination_country(cuba).
from_cuba :- origin_country(cuba).

% Main Plus is not a column of any fee table; it reads Main Cabin and takes its
% extra free bag separately.
fee_cabin(main_cabin) :- cabin(main_plus), !.
fee_cabin(C)          :- cabin(C).

pays_early_bag_fee :- fee_cabin(C), memberchk(C,[basic_economy,main_cabin]).

% ------------------------------------------------------------- First Bag
% Rows are tried in the order the statute prints them.
first_bag_fee(0)   :- \+ pays_early_bag_fee, !.
first_bag_fee(Fee) :- us_pr(S), within(S), !, Fee = 40.
first_bag_fee(Fee) :- us_pr_canada(S), within(S), !, Fee = 35.
first_bag_fee(Fee) :- to_cuba, !, ( fee_cabin(basic_economy) -> Fee = 35 ; Fee = 0 ).
first_bag_fee(0)   :- from_cuba, !.
first_bag_fee(Fee) :- touches([haiti]), !, ( fee_cabin(basic_economy) -> Fee = 35 ; Fee = 0 ).
first_bag_fee(Fee) :- touches([mexico]), !, Fee = 35.
first_bag_fee(Fee) :- guyana_suriname(S), touches(S), !, Fee = 35.
first_bag_fee(Fee) :- andean(A), touches([panama|A]), !,
                      ( fee_cabin(basic_economy) -> Fee = 45 ; Fee = 0 ).
first_bag_fee(Fee) :- other_south_america(S), touches(S), !,
                      ( fee_cabin(basic_economy) -> Fee = 60 ; Fee = 0 ).
first_bag_fee(Fee) :- europe_israel_qatar(S), touches(S), !,
                      ( fee_cabin(basic_economy) -> Fee = 75 ; Fee = 0 ).
first_bag_fee(Fee) :- long_haul_pacific(S), touches(S), !,
                      ( fee_cabin(basic_economy) -> Fee = 75 ; Fee = 0 ).
first_bag_fee(0).

% ------------------------------------------------------------ Second Bag
second_bag_fee(0)   :- \+ pays_early_bag_fee, !.
second_bag_fee(Fee) :- us_pr_canada(S), within(S), !, Fee = 45.
second_bag_fee(Fee) :- touches([honduras]), !, Fee = 45.
second_bag_fee(Fee) :- touches([haiti]), !, Fee = 65.
second_bag_fee(Fee) :- to_cuba, !, Fee = 150.
second_bag_fee(0)   :- from_cuba, !.
second_bag_fee(Fee) :- touches([mexico]), !, Fee = 45.
second_bag_fee(Fee) :- touches([panama]), !, Fee = 100.
second_bag_fee(Fee) :- guyana_suriname(S), touches(S), !, Fee = 45.
second_bag_fee(Fee) :- south_america(S), touches(S), !, Fee = 100.
second_bag_fee(Fee) :- europe_israel_qatar(S), touches(S), !, Fee = 100.
second_bag_fee(Fee) :- long_haul_pacific(S), touches(S), !, Fee = 100.
second_bag_fee(0).

% ------------------------------------------------------------- Third Bag
third_bag_fee(150) :- us_pr_canada(S), within(S), !.
third_bag_fee(0)   :- fee_cabin(first), !.
third_bag_fee(200).

% --------------------------------------------------------- Fourth Bag +
fourth_bag_fee(200).

table_fee(1,F) :- !, first_bag_fee(F).
table_fee(2,F) :- !, second_bag_fee(F).
table_fee(3,F) :- !, third_bag_fee(F).
table_fee(_,F) :- fourth_bag_fee(F).

% ------------------------------------------------------ Complimentary Bags
% The Main Cabin allowance is read off the tables: the number of leading
% positions the Main Cabin column already prices at $0.
main_cabin_allowance(0) :- first_bag_fee(F), F =\= 0, !.
main_cabin_allowance(1) :- second_bag_fee(F), F =\= 0, !.
main_cabin_allowance(2).

main_plus_allowance(N) :- cabin(main_plus), !,
                          main_cabin_allowance(A), N0 is A + 1,
                          ( N0 > 2 -> N = 2 ; N = N0 ).
main_plus_allowance(0).

% ---------------------------------- Complimentary Bags, the rest of it
% The part of the statute no case can state and no reference program
% formalizes -- 0 of 300, measured by check_shipped_rules.py.  Written here on
% the reading recorded in DEVIATIONS C1, and the one part of this file with no
% oracle of any kind behind it.
%
% The grounds do NOT stack: "the benefits are based on your highest status
% level", so the allowance is the best of them, not the sum.

status_rank(no_status,0).  status_rank(gold,1).  status_rank(platinum,2).
status_rank(platinum_pro,3).  status_rank(executive_platinum,4).

% "the benefits are based on your highest status level at time of ticketing or
% check-in" -- the statute's two bullets both come to: the higher one applies.
effective_status(S) :-
    status_at_ticketing(A), status_at_checkin(B),
    status_rank(A,RA), status_rank(B,RB),
    ( RA >= RB -> S = A ; S = B ).

status_free_bags(0) :- effective_status(no_status), !.
status_free_bags(1) :- effective_status(gold), !.
status_free_bags(2) :- effective_status(platinum), !.
status_free_bags(3).                       % platinum_pro, executive_platinum

military_free_bags(N) :- military(on_orders), !, N = 5.
military_free_bags(N) :- military(personal_travel), !, N = 3.
military_free_bags(0).

% "Confirmed Domestic First / Business / Premium Economy customers" get the
% 1st and 2nd; Flagship First and Flagship Business Plus get the 1st, 2nd and
% 3rd.  The first of those is redundant with the fee tables, which already
% price those cabins' first two bags at $0; encoded because the statute says it.
cabin_free_bags(N) :- cabin(C), memberchk(C,[first,business]), !,
                      ( flagship -> N = 3 ; N = 2 ).
cabin_free_bags(2) :- cabin(premium_economy), !.
cabin_free_bags(0).

% "or when traveling to these destinations (excluding Basic Economy)".
complimentary_first_destinations([argentina,australia,brazil,china,colombia,
    cuba,ecuador,haiti,hong_kong,india,israel,japan,new_zealand,panama,peru,
    qatar,south_korea,europe]).

destination_free_bags(0) :- fee_cabin(basic_economy), !.
destination_free_bags(1) :- complimentary_first_destinations(L),
                            destination_country(D), memberchk(D,L), !.
destination_free_bags(0).

% "Eligible AAdvantage Aviator and Citi / AAdvantage cardmembers (on domestic
% American Airlines operated itineraries)".
cardmember_free_bags(1) :- cardmember, us_pr_canada(S), within(S), !.
cardmember_free_bags(0).

free_checked_bags(N) :-
    main_plus_allowance(A), status_free_bags(B), military_free_bags(C),
    cabin_free_bags(D), destination_free_bags(E), cardmember_free_bags(F),
    max_list([A,B,C,D,E,F], N).

% The table is consulted first, always, and the allowance then waives what it
% charged.  Written the other way round -- short-circuit to $0 when the
% position is inside the allowance -- it is behaviourally identical but the
% allowance *shadows* the table: `cabin_free_bags` grants First, Business and
% Premium Economy two bags, which the tables already price at $0, so the table
% clauses stopped being reached for those cabins at all.  Same answer, but the
% authoritative rule was no longer being executed, and coverage said so.
position_fee(Pos,Fee) :-
    table_fee(Pos,T),
    free_checked_bags(F),
    ( Pos =< F -> Fee = 0 ; Fee = T ).

% --------------------------------------------------------- Weight and Size
complimentary_weight_allowance(70) :- fee_cabin(C), memberchk(C,[first,business]), !.
complimentary_weight_allowance(70) :- australasia(S), touches(S), !.
complimentary_weight_allowance(50).

oversize_fee(Dim,0)   :- Dim =< 62, !.
oversize_fee(Dim,30)  :- Dim =< 65, !.
oversize_fee(_,150)   :- south_america(SA), europe_israel_qatar(E),
                         append([panama|SA],E,S), touches(S), !.
oversize_fee(_,200).

overweight_fee(W,Allow,0)   :- W =< Allow, !.
overweight_fee(W,_,30)      :- W =< 53, !.
overweight_fee(W,_,Fee)     :- W =< 70, !, ( ( to_cuba ; from_cuba ) -> Fee = 200 ; Fee = 100 ).
% The top band has no upper bound.  The statute's table stops at 100 lbs, and
% an earlier version of this file stopped with it, returning a flat $200 above.
% RuleArena's `compute_answer.py` --- the independently written reference this
% corpus descends from --- carries the band upward instead, and a cross-check
% over the fuzzed suite found the two worlds where that differs.  The port
% follows it: `bag_accepted/1` is what records that the policy refuses the bag,
% and the fee is not asked to do that job twice.  See DEVIATIONS A3.
overweight_fee(_,_,Fee)     :- ( asia(S), touches(S) -> Fee = 450 ; Fee = 200 ).

% A bag the policy will not carry at all.
bag_accepted(Id) :-
    item(Id,_,L,W,H,Wt), Dim is L+W+H,
    Dim =< 115, Wt =< 100,
    \+ ( Wt > 70,
         ( europe_israel_qatar(S1), touches(S1) ; australasia(S2), touches(S2) ) ).

% ------------------------------------------------------------------ carry-on
% An ordinary bag must fit the box; a soft-sided garment bag has its own
% limit, and it is a sum rather than a box.
carry_on(Id) :- item(Id,ordinary_bag,L,W,H,_), L =< 22, W =< 14, H =< 9.
carry_on(Id) :- item(Id,soft_sided_garment_bag,L,W,H,_), S is L+W+H, S =< 51.

% "These don't count as your personal item or carry-on."
item_exempt(Id) :- item(Id,K,_,_,_,_),
    memberchk(K,[breast_pump,breast_milk_cooler,child_safety_seat,
                 stroller,medical_or_mobility_device]).

% "Diaper bags (1 per child)" -- the one allowance in that list with a number.
diaper_rank(Id,N) :-
    findall(J, (item(J,diaper_bag,_,_,_,_), J =< Id), Js), length(Js,N).
diaper_free(Id) :-
    item(Id,diaper_bag,_,_,_,_), diaper_rank(Id,N), children(C), N =< C.

checked_items(Is) :-
    findall(I, ( item(I,_,_,_,_,_),
                 \+ item_exempt(I), \+ diaper_free(I), \+ carry_on(I) ), Is).

% --------------------------------------------------------------- the charges
base_fees(Sum) :-
    checked_items(Is), length(Is,N),
    findall(F, (between(1,N,P), position_fee(P,F)), Fs),
    sum_list(Fs,Sum).

% The output argument must be left unbound: several of the fee predicates
% above discriminate by head unification before their guard runs, so asking
% `table_fee(3,0)` directly would skip the domestic $150 clause and succeed on
% the First-class $0 one.  This is the same shape of defect SARA's `findall/3`
% and `sum_list/2` positions have when their output is bound.
complimentary_count(C) :-
    checked_items(Is), length(Is,N),
    findall(P, (between(1,N,P), position_fee(P,F), F =:= 0), Ps),
    length(Ps,C).

% charged / complimentary excess charge for one bag
excess(Id,Allow,Fee) :-
    item(Id,_,L,W,H,Wt), Dim is L+W+H,
    oversize_fee(Dim,OS), overweight_fee(Wt,Allow,OW),
    Fee is max(OS,OW).

% The passenger may say which bags are the complimentary ones and the statute
% gives no rule, so the reading is the allocation that costs least.  The base
% fees do not depend on the allocation and each bag's saving is independent, so
% the largest savings win; ranking replaces the search.
bag_saving(Id,Sav) :-
    complimentary_weight_allowance(A),
    excess(Id,50,Charged), excess(Id,A,Comp),
    Sav is Charged - Comp.

excess_fees(Sum) :-
    checked_items(Is), complimentary_count(C),
    findall(Fee,
            ( nth1(Pos,Is,Id),
              bag_saving(Id,Sav),
              findall(1, ( nth1(P2,Is,Other),
                           bag_saving(Other,S2),
                           ( S2 > Sav ; S2 =:= Sav, P2 < Pos ) ), Better),
              length(Better,Rank),
              complimentary_weight_allowance(A),
              ( Rank < C -> excess(Id,A,Fee) ; excess(Id,50,Fee) ) ),
            Fees),
    sum_list(Fees,Sum).

accepted :- checked_items(Is), forall(member(I,Is), bag_accepted(I)).

total_cost(Total) :-
    ticket(T), base_fees(B), excess_fees(E),
    Total is T + B + E.

main :-
    total_cost(Total),
    ( accepted -> Acc = true ; Acc = false ),
    format("total_cost(~w).~naccepted(~w).~n",[Total,Acc]).
