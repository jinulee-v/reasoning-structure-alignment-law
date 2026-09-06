/* ---------------  RULES FROM THE STATUTE (only what's needed for this case) --------------- */

/* flight region for Joseph's trip */
region(domestic).      /* Austin - Denver is within the U.S. */

/* Joseph's ticket class */
class(main_plus).

/* Main Plus baggage privilege : 1 extra free checked bag (beyond Main-Cabin's 0) */
free_checked_bags(main_plus,1).

/* ---------- BASE CHECKED-BAG FEES (domestic - Main-Cabin^ rows) ---------- */
base_checked_fee(domestic,1,Fee) :- Fee = 40.
base_checked_fee(domestic,2,Fee) :- Fee = 45.
base_checked_fee(domestic,Index,Fee) :-
    Index>=3,
    ( Index=3 -> Fee = 150
    ; Index>=4 -> Fee = 200).

/* ---------- OVERSIZE SURCHARGE (domestic) ---------- */
oversize_surcharge(DimSum,S) :-
    DimSum =< 62, !, S = 0.
oversize_surcharge(DimSum,S) :-
    DimSum =< 65, !, S = 30.
oversize_surcharge(DimSum,S) :-
    DimSum =< 115, !, S = 200.

/* ---------- OVERWEIGHT SURCHARGE (domestic) ---------- */
overweight_surcharge(W,S) :-     W =< 50 , !, S = 0.
overweight_surcharge(W,S) :-     W =< 53 , !, S = 30.
overweight_surcharge(W,S) :-     W =< 70 , !, S = 100.
overweight_surcharge(W,S) :-     W =< 100, !, S = 200.

/* For a bag, surcharge is the HIGHER of oversize vs overweight */
bag_surcharge(Weight,DimSum,S) :-
    overweight_surcharge(Weight,OW),
    oversize_surcharge(DimSum,OS),
    ( OW >= OS -> S = OW ; S = OS ).


/* -----------------------  FACTS FOR JOSEPH'S CASE ----------------------- */

/* Flight ticket price */
ticket_price(173).

/* Item 1 (20*13*8, 5 lbs) is carried on - no fee, so not listed among checked bags */

/* Checked bags: id, DimSum(in), Weight(lbs) */
checked_bag(1,65,52).
checked_bag(2,65,69).
checked_bag(3,65,100).
checked_bag(4,84,52).


/* -----------------------  COST CALCULATION ----------------------- */

/* Determine the base fee for the N-th checked bag, after Main Plus free allowance */
bag_base_fee(Index,Fee) :-
    class(Class), region(domestic),
    free_checked_bags(Class,Free),
    ( Index =< Free ->                /* falls inside free allowance */
        Fee = 0
    ;   base_checked_fee(domestic,Index,Fee)
    ).

/* Fee for one checked bag = base fee + surcharge */
one_bag_total(Index,Total) :-
    checked_bag(Index,Dim,Wt),
    bag_base_fee(Index,BF),
    bag_surcharge(Wt,Dim,SF),
    Total is BF + SF.

/* Sum all checked-bag fees */
total_checked_bags_cost(Sum) :-
    findall(Cost, (checked_bag(I,_,_), one_bag_total(I,Cost)), List),
    sum_list(List,Sum).

/* Overall cost = ticket + all bag costs  (no special-needs costs in this case) */
total_cost(Total) :-
    ticket_price(P),
    total_checked_bags_cost(Bags),
    Total is P + Bags.



/* -----------------------  QUERY TO PRINT RESULT ----------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.