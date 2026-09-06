/* -------------  Statutory rules that matter for this case ------------- */

/* route type - Susan is travelling China -> U.S. */
route(china_to_us).

/* Checked-bag base fees for Basic-Economy China <-> U.S.             */
checked_fee(BagNumber, Fee) :-
    route(china_to_us),
    BagNumber =:= 1, Fee is 75.
checked_fee(BagNumber, Fee) :-
    route(china_to_us),
    BagNumber =:= 2, Fee is 100.
checked_fee(BagNumber, Fee) :-
    route(china_to_us),
    BagNumber =:= 3, Fee is 200.
checked_fee(BagNumber, Fee) :-
    route(china_to_us),
    BagNumber  >= 4,
    Fee is 200.

/* ----------  oversize / overweight fees (China <-> U.S.) ------------- */

/* oversize : size = L+W+H */
oversize_fee(Sum, Fee) :-
    Sum =< 62,                  Fee is 0.
oversize_fee(Sum, Fee) :-
    Sum  > 62,  Sum =< 65,      Fee is 30.
oversize_fee(Sum, Fee) :-
    Sum  > 65,  Sum =< 115,     Fee is 200.

/* overweight : weight in pounds */
overweight_fee(W, Fee) :-
    W =< 50,                    Fee is 0.
overweight_fee(W, Fee) :-
    W  > 50, W =< 53,           Fee is 30.
overweight_fee(W, Fee) :-
    W  > 53, W =< 70,           Fee is 100.
overweight_fee(W, Fee) :-
    W  > 70, W =< 100,          Fee is 450.

/* When both size & weight are out of limits, only the higher fee applies */
extra_fee(SumDim, Weight, Fee) :-
    oversize_fee(SumDim, OS),
    overweight_fee(Weight,  OW),
    ( OS >= OW -> Fee = OS ; Fee = OW ).

/* -------------     Cabin-baggage rules (1 carry-on free) ------------- */

carry_on_ok(L,W,H) :-
    L =< 22, W =< 14, H =< 9.

/* -----------------------  Susan's bags  ------------------------------ */
/* bag(No, Length, Width, Height, Weight).  */

bag(1, 20, 11,  7,  10).
bag(2, 38, 15, 11,  53).
bag(3, 46, 24, 23,  94).
bag(4, 38, 16, 11,  58).
bag(5, 34, 16, 14,  51).
bag(6, 41, 24, 14,  52).
bag(7, 43, 24, 15,  99).
bag(8, 34, 18, 13,  56).

/* ------------  Identify the single free carry-on item ---------------- */

free_carry_on(BagNo) :-
    bag(BagNo,L,W,H,_),
    carry_on_ok(L,W,H),
    !.      /* take the first (bag 1 in this data set) */

/* -----------------  Assemble list of checked bags -------------------- */

checked_bag_list(Checked) :-
    findall(N, (bag(N,_,_,_,_), \+ free_carry_on(N)), Checked).

/* -----------  Fee for one particular checked bag  -------------------- */

one_checked_bag_fee(BagNo, BagNumberInSequence, TotalFee) :-
    bag(BagNo, L, W, H, Weight),
    Sum is L+W+H,
    checked_fee(BagNumberInSequence, Base),      % base checked-bag fee
    extra_fee(Sum, Weight, Extra),               % oversize / overweight
    TotalFee is Base + Extra.

/* ----------  Total of ALL checked bags  ------------------------------ */

checked_bags_total(Total) :-
    checked_bag_list(List),
    findall(Fee,
            ( nth1(Index, List, BagNo),
              one_checked_bag_fee(BagNo, Index, Fee)
            ),
            Fees),
    sum_list(Fees, Total).

/* -----------------  Overall travel cost ------------------------------ */

flight_ticket(731).

total_cost(Total) :-
    flight_ticket(Tk),
    checked_bags_total(Ck),
    % no other special-needs costs in this case
    Total is Tk + Ck.

/* --------------------------  Query  ---------------------------------- */

:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.