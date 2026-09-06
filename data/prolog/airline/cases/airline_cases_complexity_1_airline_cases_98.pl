/* ---------- Rules (subset of the statutes that matter for this case) ---------- */

/* carry-on rules are irrelevant - Daniel's first (small) backpack is free */

/* size = length+width+height */
size_sum(L,W,H,S) :- S is L+W+H.

/* oversize fees on a U.S. <-> Panama (Central America) itinerary */
oversize_fee(Size,150) :- Size > 65, !.
oversize_fee(Size,30)  :- Size > 62, !.
oversize_fee(_,0).

/* overweight fees on a U.S. <-> Panama (Central America) itinerary */
overweight_fee(Weight,200) :- Weight > 70, !.
overweight_fee(Weight,100) :- Weight > 53, !.
overweight_fee(Weight,30)  :- Weight > 50, !.
overweight_fee(_,0).

/* checked-bag fees for Premium Economy on a U.S. <-> Panama itinerary          */
/* 1st & 2nd free, 3rd = $200, each bag from the 4th on = $200                */
checked_bag_fee(Index,0)   :- Index =< 2, !.
checked_bag_fee(3,200)     :- !.
checked_bag_fee(Index,200) :- Index >= 4.

/* fee for one checked piece (Index numbering the checked pieces 1...N) */
bag_fee(Index,L,W,H,Weight,Fee) :-
    size_sum(L,W,H,Size),
    oversize_fee(Size,OverSizeF),
    overweight_fee(Weight,OverWtF),
    MaxExtra is max(OverSizeF,OverWtF),           % only the higher of the two applies
    checked_bag_fee(Index,ChkF),
    Fee is ChkF + MaxExtra.

/* ----------- Facts: Daniel's seven checked pieces (carry-on omitted) ------ */
/* bag(Index,Length,Width,Height,Weight)                                      */
bag(1,50,33,24,51).
bag(2,37,15,12,87).
bag(3,34,19,12,74).
bag(4,34,17,12,95).
bag(5,38,25,13,96).
bag(6,34,20,10,54).
bag(7,47,29,20,52).

/* flight ticket cost */
flight_ticket_cost(164).

/* ------------------ summing everything up ---------------------------------- */
total_bags_fee(Total) :-
    findall(F,
            ( bag(Index,L,W,H,Wt),
              bag_fee(Index,L,W,H,Wt,F)
            ),
            Fees),
    sum_list(Fees,Total).

total_cost(Total) :-
    total_bags_fee(Bags),
    flight_ticket_cost(Tix),
    Total is Bags + Tix.

/* ------------------ query --------------------------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.