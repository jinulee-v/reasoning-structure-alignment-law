/* ===== Statutory rules that are relevant for this case ===== */

/* route involved in the case */
route(israel_us).

/* passenger cabin */
cabin(main_cabin).

/* ------------- Base checked-bag fees (Main Cabin, Israel <-> U.S.) ----------- */
base_bag_fee(israel_us, main_cabin, 1, 0).      /* 1st checked bag */
base_bag_fee(israel_us, main_cabin, 2, 100).    /* 2nd checked bag */
base_bag_fee(israel_us, main_cabin, 3, 200).    /* 3rd checked bag */
base_bag_fee(israel_us, main_cabin, n, 200).    /* 4th bag and every bag after */

/* ------------- Oversize fees (Israel <-> U.S.) ------------------------------- */
oversize_fee(israel_us, Size, 0)   :- Size =< 62.
oversize_fee(israel_us, Size, 30)  :- Size  > 62, Size =< 65.
oversize_fee(israel_us, Size, 150) :- Size  > 65, Size =< 115.

/* ------------- Over-weight fees ---------------------------------------------- */
/*  > 50-53 lbs: flat USD 30 (all routes) */
overweight_fee(_,      Weight, 30)  :- Weight  > 50, Weight =< 53.
/*  > 53-70 lbs: Israel <-> U.S. = USD 100 */
overweight_fee(israel_us, Weight, 100) :- Weight > 53, Weight =< 70.
/* =< 50 lbs: no fee */
overweight_fee(_,      Weight, 0)   :- Weight =< 50.

/* ------------- Take the higher of oversize vs overweight --------------------- */
extra_bag_fee(Route, Size, Weight, Extra) :-
    oversize_fee(Route, Size, OverSizeF),
    overweight_fee(Route, Weight, OverWtF),
    Extra is max(OverSizeF, OverWtF).

/* ------------- Carry-on rules ------------------------------------------------- */
carry_on_ok(L,W,H) :- L =< 22, W =< 14, H =< 9.

/* ===== Case facts ===== */

/* ticket price */
ticket_price(1111).

/* Bags:  bag(No,Length,Width,Height,Weight) */
bag(1,19,12,8,  9).
bag(2,53,31,28,62).
bag(3,37,24,12,52).
bag(4,37,20,11,58).
bag(5,36,23,13,53).

/* ===== Logic to compute costs ===== */

checked_bag_number(BagNo, CheckedNo) :-
    /* Bag 1 is a free carry-on; do not count it as checked
       Every other bag is counted in the order they appear */
    findall(BN,
            (bag(BN,L,W,H,_), \+ carry_on_ok(L,W,H)),
            CheckedBags),
    nth1(Index, CheckedBags, BagNo),
    ( Index =< 3 -> CheckedNo = Index
    ; CheckedNo = n ).   /* 4th or later bag => 'n' */

bag_cost(BagNo, Cost) :-
    cabin(Cab), route(Route),
    checked_bag_number(BagNo, CheckedNo),
    base_bag_fee(Route, Cab, CheckedNo, BaseFee),
    bag(BagNo,L,W,H,Wt),
    Size is L+W+H,
    extra_bag_fee(Route, Size, Wt, Extra),
    Cost is BaseFee + Extra.

total_baggage_fees(Total) :-
    findall(C,
            (bag(BN,_,_,_,_), bag_cost(BN, C)),
            Costs),
    sum_list(Costs, Total).

total_cost(Total) :-
    ticket_price(Ticket),
    total_baggage_fees(BagFees),
    Total is Ticket + BagFees.

/* ===== Query to print the answer ===== */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.