/* ---------------------------------------------------------- */
/*  Facts describing Michael's trip and his checked luggage   */
/* ---------------------------------------------------------- */

/* price of the ticket */
flight_cost(410).

/* checked bags:  bag(Id,Length,Width,Height,Weight)          */
/* (Bag #1 - the 18x12x9-inch backpack - is his carry-on and  */
/*   therefore is NOT listed here.)                           */
bag(2,39,19,18,52).
bag(3,50,29,22,67).
bag(4,34,20,10,63).
bag(5,35,16,13,53).

/* a convenient list of all checked-bag Ids */
checked_bag_ids([2,3,4,5]).

/* ---------------------------------------------------------- */
/*  Statutory rules that apply to a First-Class itinerary     */
/*  between Europe and the United States                      */
/* ---------------------------------------------------------- */

/* ---------- size (L+W+H) and weight helpers --------------- */
dims_sum(L,W,H,S) :- S is L+W+H.

/* oversize fees - Europe <--> U.S.                            */
oversize_fee(Sum,Fee) :-
       (   Sum =< 62      -> Fee = 0
       ;   Sum =< 65      -> Fee = 30
       ;   Sum =< 115     -> Fee = 150 ).

/* overweight fees                                            */
/*  - complimentary bags: 70-lb limit                         */
/*  - charged   bags: 50-lb limit                             */
overweight_fee(W,Thresh,Fee) :-
       (   W =< Thresh    -> Fee = 0
       ;   W =< 53        -> Fee = 30
       ;   W =< 70        -> Fee = 100
       ;   W =< 100       -> Fee = 200 ).

/* penalty for a single bag = the HIGHER of oversize vs       */
/* overweight (rule: "the higher fee ... applies").             */
penalty(BagId,comp,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,70,OW),        % complimentary => 70-lb limit
       Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,50,OW),        % charged bag => 50-lb limit
       Pen is max(OS,OW).

/* checked-bag fees for First Class (Europe <-> U.S.)           */
bag_fee(1,0).           % 1st, 2nd, 3rd bags are free
bag_fee(2,0).
bag_fee(3,0).
bag_fee(N,200) :- N>=4. % 4th bag and beyond

/* ---------------------------------------------------------- */
/*  Helper predicates to enumerate which bag is the "charged" */
/* ---------------------------------------------------------- */

/* pick one element from a list                               */
choose_one(List,X) :- member(X,List).

/* build an ordered list: freebies first, charged bag last    */
ordered_list(Charged,Ordered) :-
       checked_bag_ids(All),
       select(Charged,All,Freebies),   % remove the charged bag
       append(Freebies,[Charged],Ordered).

/* ---------------------------------------------------------- */
/*  Cost calculation                                          */
/* ---------------------------------------------------------- */

/* cost for a particular choice of charged bag                */
cost_for_choice(Charged,Total) :-
       ordered_list(Charged,Ordered),
       cost_bags(Ordered,1,BagCost,PenCost),
       flight_cost(Flight),
       Total is Flight + BagCost + PenCost.

/* walk through the ordered list                              */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
       (Idx =< 3 -> Type = comp ; Type = charged),
       bag_fee(Idx,Fee),
       penalty(Bag,Type,Pen),
       Next is Idx+1,
       cost_bags(Bs,Next,CostRest,PenRest),
       CostSum is Fee + CostRest,
       PenSum  is Pen + PenRest.

/* overall minimal total (there are 4 possible choices)       */
total_cost(MinTotal) :-
       checked_bag_ids(L),
       findall(T,(choose_one(L,C),cost_for_choice(C,T)),Totals),
       min_list(Totals,MinTotal).

/* ---------------------------------------------------------- */
/*  Query & output                                            */
/* ---------------------------------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n',[Total]), halt.