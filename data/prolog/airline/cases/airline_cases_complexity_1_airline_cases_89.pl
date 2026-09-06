/* ---------------  Statutory rules (abridged for this case) -------------- */

% weight limits
limit(free,   70).    % 1st - 2nd checked bags for First class
limit(paid,   50).

% oversize fees on itineraries within / between U.S., Puerto Rico, U.S.V.I., Canada
oversize_fee(Sum, 0   ) :- Sum =< 62.
oversize_fee(Sum, 30  ) :- Sum  > 62, Sum =< 65.
oversize_fee(Sum, 200 ) :- Sum  > 65, Sum =< 115.

% overweight fees for the same region
overweight_fee(W, _Kind, 0   ) :- limit(_Kind,L), W =< L.
overweight_fee(W, paid,  30  ) :- limit(paid,L), W  > L, W =< 53.
overweight_fee(W, paid,  100 ) :- limit(paid,L), W  > 53, W =< 70.
overweight_fee(W, paid,  200 ) :- W  > 70, W =< 100.
overweight_fee(W, free,  200 ) :- W  > 70, W =< 100.

% choose the higher of oversize / overweight
bag_overcharge(Sum, W, Kind, Charge) :-
    oversize_fee(Sum, OFee),
    overweight_fee(W, Kind, WFee),
    Charge is max(OFee, WFee).

/* --------------------------  Case facts  ------------------------------- */

% bag(Id, L, W, H, Weight).
bag(b2, 33,20,12,64).
bag(b3, 37,15,12,88).
bag(b4, 44,32,22,52).
bag(b5, 35,14,14,57).
bag(b6, 47,27,24,93).
bag(b7, 37,13,13,64).
bag(b8, 37,12,14,53).

all_bags([b2,b3,b4,b5,b6,b7,b8]).

flight_ticket(100).

/* ----------------  Cost of a particular bag list ----------------------- */

% charge for a bag that is counted against the free allowance
free_bag_cost(Id, Cost) :-
    bag(Id,L,W,H,Weight),
    Sum is L+W+H,
    bag_overcharge(Sum,Weight,free,Cost).

% charge for a paid bag; Position is 1 for the 3rd bag, 2 for the 4th, etc.
paid_bag_cost(Position, Id, Cost) :-
    bag(Id,L,W,H,Weight),
    Sum  is L+W+H,
    bag_overcharge(Sum,Weight,paid,OCost),
    bag_fee(Position,BagFee),
    Cost is BagFee + OCost.

bag_fee(1,150).                % 3rd checked bag
bag_fee(Pos,200) :- Pos >= 2.  % 4th and beyond

/* ------------------  Enumerate all possibilities ----------------------- */

combo(Complimentary, Paid) :-
    all_bags(Bags),
    select(Comp1,Bags,R1),
    select(Comp2,R1,Paid),
    Complimentary = [Comp1,Comp2].

cost_for_choice(Complimentary, Paid, TotalCost) :-
    maplist(free_bag_cost, Complimentary, FreeCosts),
    sumlist(FreeCosts, FreeTotal),

    findall(C, (nth1(Pos, Paid, Id), paid_bag_cost(Pos,Id,C)), PaidCosts),
    sumlist(PaidCosts, PaidTotal),

    flight_ticket(Ticket),
    TotalCost is Ticket + FreeTotal + PaidTotal.

/* --------------------  Minimal total cost ------------------------------ */

total_cost(MinCost) :-
    setof(Cost, Comp^Paid^(combo(Comp, Paid), cost_for_choice(Comp, Paid, Cost)), [MinCost|_]).

/* ---------------------------  Query  ----------------------------------- */

:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.