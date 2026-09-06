/* ----------  Statutory rules (relevant excerpts) ---------- */

% Route and service class for the itinerary
route(europe_us).
service_class(basic_economy).

% Fare of the ticket itself
ticket_cost(630).

/* ----------  Baggage brought by the passenger ------------- */

% bag(ID, Length, Width, Height, Weight).
bag(1, 19, 14,  9,  7).   % intended carry-on
bag(2, 36, 17, 10, 51).
bag(3, 33, 22,  9, 52).
bag(4, 44, 31, 23, 68).
bag(5, 36, 19,  9, 52).
bag(6, 34, 19, 11, 57).
bag(7, 36, 16, 13, 65).
bag(8, 40, 17, 17, 65).

/* ----------  Helper predicates ---------------------------- */

% total outside dimensions of a bag
size(BagID, Size) :-
    bag(BagID,L,W,H,_),
    Size is L + W + H.

% weight of a bag
weight(BagID, W) :- bag(BagID,_,_,_,W).

/* ----------  Free carry-on test --------------------------- */

carry_on(BagID) :-
    bag(BagID,L,W,H,_),
    L =< 22, W =< 14, H =< 9.

/* ----------  Checked-bag list in ordinal order ------------ */

checked_bag_list(List) :-
    findall(ID,
            (bag(ID,_,_,_,_), \+ carry_on(ID)),
            IDs),
    sort(IDs, List).              % ascending order 2 ... 8

/* ----------  Base checked-bag fee by ordinal -------------- */

base_fee(1,  75).   % 1st bag, Basic Econ, Europe <-> US
base_fee(2, 100).   % 2nd bag
base_fee(3, 200).   % 3rd bag
base_fee(N, 200) :- N >= 4.   % 4th bag and beyond

/* ----------  Over-weight surcharges ----------------------- */

weight_surcharge(BagID, 30) :-         % 50 < w =< 53 lb
    weight(BagID,W), W  > 50, W =< 53.
weight_surcharge(BagID,100) :-         % 53 < w =< 70 lb, Europe <-> US
    weight(BagID,W), W  > 53, W =< 70, route(europe_us).
weight_surcharge(BagID,0)  :-          % at or below 50 lb
    weight(BagID,W), W =< 50.

/* ----------  Over-size surcharges ------------------------- */

oversize_surcharge(BagID,30) :-        % 62 < s =< 65 in
    size(BagID,S), S  > 62, S =< 65.
oversize_surcharge(BagID,150) :-       % 65 < s =< 115 in, Europe <-> US
    size(BagID,S), S  > 65, S =< 115, route(europe_us).
oversize_surcharge(BagID,0) :-         % within 62-in limit
    size(BagID,S), S =< 62.

/* ----------  Highest applicable surcharge ----------------- */

bag_surcharge(BagID, S) :-
    weight_surcharge(BagID, WFee),
    oversize_surcharge(BagID, OFee),
    ( WFee >= OFee -> S = WFee ; S = OFee ).

/* ----------  Cost of each checked bag --------------------- */

bag_cost(BagID, Ordinal, Cost) :-
    base_fee(Ordinal, Base),
    bag_surcharge(BagID, Surch),
    Cost is Base + Surch.

/* ----------  Aggregate baggage cost ----------------------- */

total_bags_cost(Total) :-
    checked_bag_list(Checked),
    bag_costs(Checked, 1, Total).

bag_costs([], _, 0).
bag_costs([B|Rest], Ord, Total) :-
    bag_cost(B, Ord, C1),
    Next is Ord + 1,
    bag_costs(Rest, Next, CRest),
    Total is C1 + CRest.

/* ----------  Overall total cost --------------------------- */

total_cost(Total) :-
    ticket_cost(Ticket),
    total_bags_cost(BagFees),
    Total is Ticket + BagFees.

:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.