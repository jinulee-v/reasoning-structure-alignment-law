:- format("~w~n", ["Label: 1317"]).
/*-----------------------------------------------------------
   American Airlines - baggage and ticket cost calculator
   Case:  Jessica - Seattle (SEA) -> Miami (MIA), Main Plus
-----------------------------------------------------------*/

/* ----------  ticket -------------------------------------- */
flight_cost(292).


/* ----------  list of checked bags  ----------------------- */
/* bag(Id,Length,Width,Height,Weight).                      */
/* (Jessica's backpack that is 22x12x7, 5 lbs is her carry-on,
   therefore it is NOT listed here.)                        */
bag(2,51,29,24,51).
bag(3,46,25,21,63).
bag(4,47,35,24,75).
bag(5,34,22, 9,53).

/* list (constant) of all checked-bag Ids (order given) */
checked_bag_ids([2,3,4,5]).

/* ----------  Statutory rules (domestic, Main Plus)  ------- */

/* sum of dimensions */
dims_sum(L,W,H,S) :- S is L+W+H.

/* oversize fee - Within / between U.S., Canada, PR, USVI */
oversize_fee(Sum,Fee) :-
       (   Sum =< 62      -> Fee = 0
       ;   Sum =< 65      -> Fee = 30
       ;   Sum =< 115     -> Fee = 200 ).

/* overweight fee - domestic
   Threshold is 70 lbs for COMPLIMENTARY bags, 50 lbs for CHARGED */
overweight_fee(W,Thresh,Fee) :-
       (   W =< Thresh        -> Fee = 0
       ;   W =< 53            -> Fee = 30
       ;   W =< 70            -> Fee = 100
       ;   W =< 100           -> Fee = 200 ).

/* penalty for one bag: higher of over-size vs over-weight */
penalty(BagId,comp,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,70,OW),   % complimentary => 70-lb limit
       Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,50,OW),   % charged bag => 50-lb limit
       Pen is max(OS,OW).

/* checked-bag base fee by ordinal position - Main Plus (domestic) */
bag_fee(1,0).                  % extra free bag that Main Plus includes
bag_fee(2,45).                 % 2nd checked bag
bag_fee(3,150).                % 3rd
bag_fee(N,200) :- N>=4.        % 4th and beyond

/* ----------  Helper predicates --------------------------- */

/* choose exactly 1 element Free from the list */
choose_one([X|_],X).
choose_one([_|T],X) :- choose_one(T,X).

/* build ordered list putting Free first, others keep order */
ordered_list(Free,Ordered) :-
       checked_bag_ids(All),
       select(Free,All,Rest),
       Ordered = [Free|Rest].

/* compute cost for a particular choice of complimentary bag */
cost_for_choice(Free,Total) :-
       ordered_list(Free,Ordered),
       cost_bags(Ordered,1,CostBags,Penalties),
       flight_cost(Flight),
       Total is Flight + CostBags + Penalties.

/* walk through ordered list accumulating fees and penalties */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
       (Idx =:= 1 -> Type = comp ; Type = charged),
       bag_fee(Idx,Fee),
       penalty(Bag,Type,Pen),
       NextIdx is Idx+1,
       cost_bags(Bs,NextIdx,CostRest,PenRest),
       CostSum is Fee + CostRest,
       PenSum  is Pen + PenRest.

/* minimal total cost over all ways of choosing the free bag */
total_cost(MinTotal) :-
       checked_bag_ids(L),
       findall(T,
               ( choose_one(L,F),
                 cost_for_choice(F,T)),
               Totals),
       min_list(Totals,MinTotal).

/* ----------  Query and report ---------------------------- */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.