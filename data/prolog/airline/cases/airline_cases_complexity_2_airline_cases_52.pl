/* =========================================================
   Facts for James - Business Class, Lima (Peru) -> Denver
   ========================================================= */

/* ticket price */
flight_cost(533).

/* checked bags: bag(Id,Length,Width,Height,Weight) */
bag(2,34,20,10,51).
bag(3,49,33,27,88).
bag(4,37,17, 9,61).
bag(5,43,29,20,53).
bag(6,33,20,12,52).
bag(7,35,20, 9,56).
bag(8,36,17,10,87).
bag(9,51,32,29,53).
bag(10,34,18,12,94).
bag(11,54,32,27,57).

/* list of all checked-bag Ids (carry-on already accounted for) */
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).

/* =========================================================
   Statutory rules for this itinerary
   (South America <-> U.S. - Business Class)
   ========================================================= */

/* dimensional sum */
dims_sum(L,W,H,S) :- S is L+W+H.

/* oversize fee: South America (except Guyana/Suriname) <-> U.S. */
oversize_fee(S,Fee) :-
      (  S =< 62  -> Fee = 0
      ;  S =< 65  -> Fee = 30
      ;  S =< 115 -> Fee = 150 ).

/* overweight fee
   - complimentary bags: 70-lb allowance
   - charged bags:       50-lb allowance                 */
overweight_fee(W,Thresh,Fee) :-
      (  W =< Thresh -> Fee = 0
      ;  W =< 53     -> Fee = 30
      ;  W =< 70     -> Fee = 100
      ;  W =< 100    -> Fee = 200 ).

/* penalty = higher of oversize vs overweight */
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

/* checked-bag base fee (Business Class, Peru <-> U.S.) */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(N,200) :- N >= 3.

/* =========================================================
   Helper predicates
   ========================================================= */

/* choose two distinct elements (F1 < F2) from a list */
choose_two(List,F1,F2) :-
      append(_, [F1|Rest], List),
      member(F2, Rest).

/* build ordered list: freebies first, remaining in original order */
ordered_list(F1,F2,Ordered) :-
      checked_bag_ids(All),
      select(F1,All,R1),
      select(F2,R1,R),
      Ordered = [F1,F2|R].

/* cost for a specific choice of the 2 complimentary bags */
cost_for_choice(F1,F2,Total) :-
      ordered_list(F1,F2,Ordered),
      bags_cost(Ordered,1,BaseFees,Penalties),
      flight_cost(Flight),
      Total is Flight + BaseFees + Penalties.

/* walk through list, accumulating base fees and penalties */
bags_cost([],_,0,0).
bags_cost([Bag|Bs],Idx,BaseSum,PenSum) :-
      (Idx =< 2 -> Type = comp ; Type = charged),
      bag_fee(Idx,BFee),
      penalty(Bag,Type,Pen),
      Idx1 is Idx + 1,
      bags_cost(Bs,Idx1,BaseRest,PenRest),
      BaseSum is BFee + BaseRest,
      PenSum  is Pen  + PenRest.

/* find minimal total cost over all ways of picking the 2 freebies */
compute_total(Min) :-
      checked_bag_ids(L),
      findall(T,
              ( choose_two(L,F1,F2),
                cost_for_choice(F1,F2,T) ),
              Totals),
      min_list(Totals,Min).

/* =========================================================
   Query & output
   ========================================================= */
:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.