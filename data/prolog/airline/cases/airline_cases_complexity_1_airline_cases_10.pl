/* ---------------------------------------------------------- */
/*  Facts describing Daniel's itinerary and his checked bags  */
/* ---------------------------------------------------------- */

flight_cost(1249).                    /* ticket price - USD */

/* bag(Id, Length, Width, Height, Weight in pounds)           */
bag(2,45,28,19,75).
bag(3,36,20, 9,70).
bag(4,38,15,16,52).
bag(5,33,22,10,52).
bag(6,38,14,12,57).
bag(7,33,17,14,69).
bag(8,44,30,19,91).

/* list of all checked-bag Ids (carry-on bag #1 is excluded)  */
checked_bag_ids([2,3,4,5,6,7,8]).

/* ---------------------------------------------------------- */
/*  Statutory rules that apply to a Business-class itinerary  */
/*  between China and the United States                       */
/* ---------------------------------------------------------- */

/* sum of the three outside dimensions                        */
dims_sum(L,W,H,S) :- S is L+W+H.

/* oversize fees - China / Japan / Korea / HK / India / Aus / NZ */
oversize_fee(Sum,Fee) :-
       (   Sum =< 62      -> Fee = 0
       ;   Sum =< 65      -> Fee = 30
       ;   Sum =< 115     -> Fee = 200 ).

/* overweight fees                                            */
/*  - complimentary bags => 70-lb threshold                    */
/*  - charged bags        => 50-lb threshold                    */
/*  - special band 70-100 lbs on this route costs $450        */
overweight_fee(W,Thresh,Fee) :-
       (   W =< Thresh -> Fee = 0
       ;   W =< 53     -> Fee = 30
       ;   W =< 70     -> Fee = 100
       ;   W =< 100    -> Fee = 450 ).

/* penalty for a particular bag: higher of oversize vs overweight */
penalty(BagId,comp,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,70,OW),          % complimentary => 70-lb limit
       Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,50,OW),          % charged bag => 50-lb limit
       Pen is max(OS,OW).

/* checked-bag fees for Business class on this route          */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(3,200).
bag_fee(4,200).
bag_fee(5,200).
bag_fee(6,200).
bag_fee(7,200).
bag_fee(8,200).

/* ---------------------------------------------------------- */
/*  Helper predicates                                          */
/* ---------------------------------------------------------- */

/* select two different elements (F1 < F2) from a list        */
choose_two(List,F1,F2) :-
       append(_,[F1|Tail],List),
       member(F2,Tail).

/* put the two free bags in positions 1 and 2, retain order   */
ordered_list(F1,F2,Ordered) :-
       checked_bag_ids(All),
       select(F1,All,Rest1),
       select(F2,Rest1,Rest),
       Ordered = [F1,F2|Rest].                 % freebies first

/* accumulate costs for a specific ordering                   */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
       (Idx =< 2 -> Type = comp ; Type = charged),
       bag_fee(Idx,Fee),
       penalty(Bag,Type,Pen),
       NextIdx is Idx + 1,
       cost_bags(Bs,NextIdx,CostRest,PenRest),
       CostSum is Fee + CostRest,
       PenSum  is Pen + PenRest.

/* total cost for a particular choice of the 2 complimentary bags */
cost_for_choice(F1,F2,Total) :-
       ordered_list(F1,F2,Ordered),
       cost_bags(Ordered,1,CostBags,Penalties),
       flight_cost(Flight),
       Total is Flight + CostBags + Penalties.

/* compute the minimal total cost over all ways of picking the 2 freebies */
compute_total(MinTotal) :-
       checked_bag_ids(L),
       findall(T,
               ( choose_two(L,F1,F2),
                 cost_for_choice(F1,F2,T)),
               Totals),
       min_list(Totals,MinTotal).

/* ---------------------------------------------------------- */
/*  Run the query and print the result                        */
/* ---------------------------------------------------------- */
:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.