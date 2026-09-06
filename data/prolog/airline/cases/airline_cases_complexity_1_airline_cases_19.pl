/* ---------- Facts describing the passenger, flight and bags ---------- */

% flight(origin, destination, cabin_class, ticket_price).
flight(orlando, port_au_prince, premium_economy, 59).

% Checked bag order (the first 2 bags are the "free-allowance" bags)
checked_bag_order([bag3, bag4, bag2, bag5, bag6, bag7, bag8]).

% bag(Id, Length, Width, Height, Weight).
bag(bag1, 18, 12,  9,  7).      % carry-on - will not be checked
bag(bag2, 37, 19,  9, 51).
bag(bag3, 37, 14, 13, 100).
bag(bag4, 45, 22, 17, 51).
bag(bag5, 37, 16, 10, 51).
bag(bag6, 33, 17, 13, 78).
bag(bag7, 34, 21,  9, 51).
bag(bag8, 35, 16, 12, 53).

/* ---------- Helpers ---------- */

dimensions_sum(Id, Sum) :-
    bag(Id, L, W, H, _),
    Sum is L + W + H.

weight(Id, W) :-
    bag(Id, _, _, _, W).

/* ---------- Base checked-bag fees for Premium Economy on a U.S. <-> Haiti flight ---------- */
/* 1st & 2nd bags free, every bag from the 3rd onward costs $200           */

base_checked_fee(Position, 0)  :- Position =< 2.      % first 2 bags free
base_checked_fee(Position,200) :- Position  > 2.      % 3rd+ = $200

/* ---------- Oversize fee (Caribbean route) ---------- */
/* Over 62"-65": $30 ; 65"-115": $200 ; =<62": $0        */

oversize_fee(Id, Fee) :-
    dimensions_sum(Id, Sum),
    ( Sum =< 62 -> Fee = 0
    ; Sum =< 65 -> Fee = 30
    ; Sum =<115 -> Fee = 200
    ;                Fail = true, fail               % larger not accepted
    ).

/* ---------- Overweight fee (Caribbean route) ---------- */
/* >50-53 lb: $30 ; >53-70 lb: $100 ; >70-100 lb: $200   */

overweight_fee(Id, Fee) :-
    weight(Id, W),
    ( W =< 50     -> Fee = 0
    ; W =< 53     -> Fee = 30
    ; W =< 70     -> Fee = 100
    ; W =< 100    -> Fee = 200
    ;                 Fail = true, fail               % heavier not accepted
    ).

/* ---------- Total cost per checked bag ---------- */

bag_cost(Position, Id, Cost) :-
    base_checked_fee(Position, Base),
    oversize_fee(Id, OSize),
    overweight_fee(Id, OWeight),
    MaxExtra is max(OSize, OWeight),
    Cost is Base + MaxExtra.

/* ---------- Sum all checked-bag costs ---------- */

all_bags_cost(Total) :-
    checked_bag_order(Ids),
    findall(Cost,
        (nth1(Pos, Ids, Id), bag_cost(Pos, Id, Cost)),
        Costs),
    sum_list(Costs, Total).

/* ---------- Grand total: ticket + bags ---------- */

total_cost(GrandTotal) :-
    flight(_, _, _, Ticket),
    all_bags_cost(Bags),
    GrandTotal is Ticket + Bags.

/* ---------- Query ---------- */

:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.