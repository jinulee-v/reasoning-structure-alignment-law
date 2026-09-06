:- format("~w~n", ["Label: 2425"]).
/* =========================================================
   Patricia - Austin (U.S.)  ->  Quito (Ecuador / S. America)
   Cabin: Business
   Itinerary region: Between U.S. and South America
   ========================================================= */

/* ----------------  Cost of the flight ticket  ------------ */
flight_cost(535).

/* ----------------  Bags brought on the trip -------------- */
/* Format: bag(Id,Length,Width,Height,Weight).               */
/* Bag 1 fits the carry-on limits and is therefore excluded  */
/* from the checked-bag calculations.                       */
bag(2,40,23,19,78).
bag(3,36,14,13,52).
bag(4,38,15,12,61).
bag(5,50,34,25,77).
bag(6,34,20,10,75).
bag(7,35,17,13,52).
bag(8,54,29,31,79).

/* All checked-bag Ids in a fixed order (smallest Id ...)      */
checked_bag_ids([2,3,4,5,6,7,8]).

/* ---------------- Statutory Rules (region-specific) ------- */

/* Sum of the 3 outside dimensions of a bag */
dims_sum(L,W,H,S) :- S is L+W+H.

/* Oversize fees - Panama / South America (except Guyana / Suriname) */
oversize_fee(Sum,Fee) :-
       (   Sum =< 62      -> Fee = 0
       ;   Sum =< 65      -> Fee = 30            % 62-65 in / 158-165 cm
       ;   Sum =< 115     -> Fee = 150 ).        % 65-115 in / 165-292 cm

/* Overweight fees (all regions except Cuba)                 */
/* Threshold 70 lbs for complimentary Business bags          */
/* Threshold 50 lbs for all charged bags                     */
overweight_fee(W,Thresh,Fee) :-
       (   W =< Thresh    -> Fee = 0
       ;   W =< 53        -> Fee = 30
       ;   W =< 70        -> Fee = 100
       ;   W =< 100       -> Fee = 200 ).

/* Penalty = higher of the two (oversize vs overweight)      */
penalty(BagId,comp,Pen) :-
       bag(BagId,L,W,H,Wt),
       dims_sum(L,W,H,S),
       oversize_fee(S,OS),
       overweight_fee(Wt,70,OW),        % 70-lb limit for complimentary bags
       Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
       bag(BagId,L,W,H,Wt),
       dims_sum(L,W,H,S),
       oversize_fee(S,OS),
       overweight_fee(Wt,50,OW),        % 50-lb limit for charged bags
       Pen is max(OS,OW).

/* Checked-bag fees (Business class, U.S. <-> South America)   */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(N,200) :- N>=3.

/* ---------------  Helper predicates  --------------------- */

/* Choose 2 different elements (F1 before F2) from a list    */
choose_two(List,F1,F2) :-
       append(_,[F1|Tail],List),
       member(F2,Tail).

/* Place the 2 free bags at positions 1 and 2                */
ordered_list(F1,F2,Ordered) :-
       checked_bag_ids(All),
       select(F1,All,Rest1),
       select(F2,Rest1,Rest),
       Ordered = [F1,F2|Rest].

/* Cost produced by a particular choice of complimentary bags */
cost_for_choice(F1,F2,Total) :-
       ordered_list(F1,F2,Ordered),
       bags_cost(Ordered,1,BagsFee,Penalties),
       flight_cost(Tix),
       Total is Tix + BagsFee + Penalties.

/* Traverse ordered list, accumulating bag fees & penalties  */
bags_cost([],_,0,0).
bags_cost([Bag|Bs],Idx,FeeSum,PenSum) :-
       (Idx =< 2 -> Kind = comp ; Kind = charged),
       bag_fee(Idx,BFee),
       penalty(Bag,Kind,Pen),
       Next is Idx+1,
       bags_cost(Bs,Next,FRest,PRest),
       FeeSum is BFee + FRest,
       PenSum is Pen + PRest.

/* Overall minimal total cost (best choice of freebies)      */
total_cost(MinTotal) :-
       checked_bag_ids(Ids),
       findall(T,
               ( choose_two(Ids,F1,F2),
                 cost_for_choice(F1,F2,T)),
               Totals),
       min_list(Totals,MinTotal).

/* --------------------  Query  ----------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.