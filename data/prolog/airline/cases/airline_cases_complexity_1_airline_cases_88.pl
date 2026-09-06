:- format("~w~n", ["Label: 2147"]).
/* ------------------------------------------------------------------
   Itinerary facts : Robert - First Class - Lima (Peru) -> Las Vegas
   ------------------------------------------------------------------ */

/* ticket price */
flight_cost(267).

/* checked bags: bag(Id,Length,Width,Height,Weight) */
bag(2,47,25,24,79).
bag(3,47,25,25,65).
bag(4,36,14,14,77).
bag(5,53,32,29,53).
bag(6,35,15,14,61).
bag(7,37,25,12,51).
bag(8,36,17,12,78).

/* list of all checked-bag Ids */
checked_bag_ids([2,3,4,5,6,7,8]).

/* ------------------------------------------------------------------
   Statutory rules for a South-America <-> U.S. itinerary (First Class)
   ------------------------------------------------------------------ */

/* linear-dimension sum */
dims_sum(L,W,H,S) :- S is L+W+H.

/* -----------------------  Oversize fees  -------------------------- */
/* Route category: "Panama / South America (except Guyana / Suriname)" */
oversize_fee(Sum,Fee) :-
         (  Sum =< 62      -> Fee = 0
         ;  Sum =< 65      -> Fee = 30
         ;  Sum =< 115     -> Fee = 150).

/* -----------------------  Overweight fees  ------------------------ */
/* generic rule with variable threshold (70 lb for complimentary bags,
   50 lb otherwise)                                                  */
overweight_fee(W,Thresh,Fee) :-
         (  W =< Thresh    -> Fee = 0
         ;  W =< 53        -> Fee = 30
         ;  W =< 70        -> Fee = 100
         ;  W =< 100       -> Fee = 200 ).

/* -----------------------  Bag penalty  ---------------------------- */
/* penalty = max(oversize, overweight)                               */
penalty(BagId,comp,Pen) :-
         bag(BagId,L,W,H,Weight),
         dims_sum(L,W,H,Sum),
         oversize_fee(Sum,OS),
         overweight_fee(Weight,70,OW),     % complimentary => 70-lb limit
         Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
         bag(BagId,L,W,H,Weight),
         dims_sum(L,W,H,Sum),
         oversize_fee(Sum,OS),
         overweight_fee(Weight,50,OW),     % charged bag => 50-lb limit
         Pen is max(OS,OW).

/* -----------------------  Base checked-bag fees ------------------- */
/* First Class - South America <-> U.S.                                */
bag_fee(Pos,0)  :- Pos =< 3.          % 1st - 3rd bags complimentary
bag_fee(Pos,200):- Pos  > 3.          % 4th bag and beyond           

/* ------------------------------------------------------------------
   Helper predicates
   ------------------------------------------------------------------ */

/* choose three different elements (F1<F2<F3) from a list */
choose_three(List,F1,F2,F3) :-
         append(_,[F1|Rest1],List),
         append(_,[F2|Rest2],Rest1),
         member(F3,Rest2).

/* place the 3 selected complimentary bags first in the ordered list */
ordered_list(F1,F2,F3,Ordered) :-
         checked_bag_ids(All),
         select(F1,All,R1),
         select(F2,R1,R2),
         select(F3,R2,Rest),
         Ordered = [F1,F2,F3|Rest].

/* walk through ordered list adding base fees and penalties */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,FeeSum,PenSum) :-
         (Idx =< 3 -> Type = comp ; Type = charged),
         bag_fee(Idx,BFee),
         penalty(Bag,Type,Pen),
         Next is Idx+1,
         cost_bags(Bs,Next,FRest,PRest),
         FeeSum is BFee + FRest,
         PenSum  is Pen   + PRest.

/* cost for one particular selection of 3 complimentary bags */
cost_for_choice(F1,F2,F3,Total) :-
         ordered_list(F1,F2,F3,Ordered),
         cost_bags(Ordered,1,BaseFees,Penalties),
         flight_cost(Tix),
         Total is Tix + BaseFees + Penalties.

/* compute minimal total cost by trying every combination of 3 freebies */
total_cost(MinTotal) :-
         checked_bag_ids(L),
         findall(T,
                 ( choose_three(L,F1,F2,F3),
                   cost_for_choice(F1,F2,F3,T)),
                 Totals),
         min_list(Totals,MinTotal).

/* ------------------------------------------------------------------
   Query & output
   ------------------------------------------------------------------ */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.