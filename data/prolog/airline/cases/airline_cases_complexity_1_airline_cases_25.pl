:- format("~w~n", ["Label: 2421"]).
/* =========================================================
   Susan - Business Class
   Los Angeles (U.S.)  ->  Ottawa (Canada)
   Route type: Within / between U.S. and Canada
   ========================================================= */

/* ----------------  Ticket  ------------------------------ */
flight_cost(241).


/* ----------------  Bags --------------------------------- */
/* bag(Id,Length,Width,Height,Weight)                       */
bag(2,43,20,21,76).      /* luggage box */
bag(3,37,19,14,53).      /* backpack    */
bag(4,35,16,12,67).      /* luggage box */
bag(5,49,23,24,73).      /* luggage box */
bag(6,40,23,21,63).      /* luggage box */
bag(7,47,29,19,58).      /* backpack    */
bag(8,52,30,28,52).      /* backpack    */

/* list of all checked-bag Ids (carry-on excluded)          */
checked_bag_ids([2,3,4,5,6,7,8]).

/* ----------------  Statutory rules ---------------------- */

/* Sum of outside dimensions                                */
dims_sum(L,W,H,S) :- S is L+W+H.

/* ---------------------------------------------------------
   Oversize fees  -  within / between U.S. and Canada
   --------------------------------------------------------- */
oversize_fee(Sum,Fee) :-
       (   Sum =< 62      -> Fee = 0
       ;   Sum =< 65      -> Fee = 30
       ;   Sum =< 115     -> Fee = 200 ).

/* ---------------------------------------------------------
   Overweight fees
   Thresh = 70 lbs for complimentary bags
            50 lbs for charged (fee-bearing) bags
   --------------------------------------------------------- */
overweight_fee(W,Thresh,Fee) :-
       (   W =< Thresh        -> Fee = 0
       ;   W =< 53            -> Fee = 30
       ;   W =< 70            -> Fee = 100
       ;   W =< 100           -> Fee = 200 ).

/* ---------------------------------------------------------
   Penalty for a bag  =  higher of (oversize vs overweight)
   --------------------------------------------------------- */
penalty(BagId,comp,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,70,OW),           % complimentary
       Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,50,OW),           % charged
       Pen is max(OS,OW).

/* ---------------------------------------------------------
   Checked-bag base fees - Business Class
   (within / between U.S. and Canada)
   --------------------------------------------------------- */
bag_fee(1,0).        % 1st bag  free
bag_fee(2,0).        % 2nd bag  free
bag_fee(3,150).
bag_fee(N,200) :- N >= 4.

/* ----------------  Helper predicates -------------------- */

/* choose two different elements (F1<F2) from a list         */
choose_two(List,F1,F2) :-
       append(_,[F1|Tail],List),
       member(F2,Tail).

/* build ordered list with the 2 complimentary bags first    */
ordered_list(F1,F2,Ordered) :-
       checked_bag_ids(All),
       select(F1,All,Rest1),
       select(F2,Rest1,Rest),
       Ordered = [F1,F2|Rest].

/* cost for a particular choice of complimentary bags        */
cost_for_choice(F1,F2,Total) :-
       ordered_list(F1,F2,Ordered),
       bags_cost(Ordered,1,BaseFees,Penalties),
       flight_cost(Flight),
       Total is Flight + BaseFees + Penalties.

/* walk through ordered list, accumulating fees and penalties*/
bags_cost([],_,0,0).
bags_cost([Bag|Bs],Idx,BaseSum,PenSum) :-
       (Idx =< 2 -> Type = comp ; Type = charged),
       bag_fee(Idx,Fee),
       penalty(Bag,Type,Pen),
       NextIdx is Idx + 1,
       bags_cost(Bs,NextIdx,BaseRest,PenRest),
       BaseSum is Fee + BaseRest,
       PenSum  is Pen + PenRest.

/* ----------------  Grand-total (minimal) ----------------- */
total_cost(MinTotal) :-
       checked_bag_ids(L),
       findall(T,
               ( choose_two(L,F1,F2),
                 cost_for_choice(F1,F2,T)),
               Totals),
       min_list(Totals,MinTotal).

/* ----------------  Query & Output ------------------------ */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.