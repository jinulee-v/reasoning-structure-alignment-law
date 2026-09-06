:- format("~w~n", ["Label: 2880"]).
/* -------------  Trip facts (Mary) --------------------------- */

/* Base ticket cost */
flight_cost(180).

/* Checked bags:  bag(Id,Length,Width,Height,Weight) */
bag(2,46,20,22,56).
bag(3,46,25,22,53).
bag(4,35,16,14,67).
bag(5,34,17,13,51).
bag(6,53,31,30,51).
bag(7,35,15,14,63).
bag(8,42,18,18,76).
bag(9,38,11,14,52).
bag(10,33,20,12,51).
bag(11,42,17,19,54).

/* List of all checked-bag IDs (carry-on already excluded) */
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).

/* -------------  Statutory rules (domestic, Business) -------- */

/* Sum of dimensions */
dims_sum(L,W,H,S) :- S is L+W+H.

/* Oversize fee - within / between U.S. & Canada / PR / USVI */
oversize_fee(S,Fee) :-
    ( S =< 62  -> Fee = 0
    ; S =< 65  -> Fee = 30
    ; S =< 115 -> Fee = 200).

/* Overweight fee
   Thresh = 70 lbs for complimentary bags, 50 lbs for charged bags */
overweight_fee(W,Thresh,Fee) :-
    ( W =< Thresh -> Fee = 0
    ; W =< 53     -> Fee = 30
    ; W =< 70     -> Fee = 100
    ; W =< 100    -> Fee = 200).

/* Penalty = higher of oversize vs overweight */
penalty(BagId,comp,Pen) :-
    bag(BagId,L,W,H,Wt),
    dims_sum(L,W,H,S),
    oversize_fee(S,OS),
    overweight_fee(Wt,70,OW),
    Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
    bag(BagId,L,W,H,Wt),
    dims_sum(L,W,H,S),
    oversize_fee(S,OS),
    overweight_fee(Wt,50,OW),
    Pen is max(OS,OW).

/* Checked-bag fees for Business Class, domestic */
bag_fee(1,0).           /* 1st & 2nd complimentary            */
bag_fee(2,0).
bag_fee(3,150).         /* 3rd bag                            */
bag_fee(N,200) :- N>=4. /* 4th bag and beyond                 */

/* -------------  Helper predicates --------------------------- */

/* Choose 2 different freebies from a list (F1 comes before F2) */
choose_two(List,F1,F2) :-
    append(_,[F1|Tail],List),
    member(F2,Tail).

/* Build the ordered list: freebies in positions 1 and 2 */
ordered_list(F1,F2,Ordered) :-
    checked_bag_ids(All),
    select(F1,All,R1),
    select(F2,R1,R),
    Ordered = [F1,F2|R].

/* Cost for one particular choice of freebies */
cost_for_choice(F1,F2,Total) :-
    ordered_list(F1,F2,Ordered),
    cost_bags(Ordered,1,FeeSum,PenSum),
    flight_cost(Tix),
    Total is Tix + FeeSum + PenSum.

/* Walk through ordered list accumulating bag fees + penalties */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,FeeTot,PenTot) :-
    (Idx =< 2 -> Type = comp ; Type = charged),
    bag_fee(Idx,Fee),
    penalty(Bag,Type,Pen),
    Next is Idx+1,
    cost_bags(Bs,Next,FeeRest,PenRest),
    FeeTot is Fee + FeeRest,
    PenTot  is Pen + PenRest.

/* Minimal total over all ways of picking 2 complimentary bags */
total_cost(MinTotal) :-
    checked_bag_ids(L),
    findall(T,(choose_two(L,F1,F2),cost_for_choice(F1,F2,T)),Ts),
    min_list(Ts,MinTotal).

/* -------------  Query & output ------------------------------ */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.