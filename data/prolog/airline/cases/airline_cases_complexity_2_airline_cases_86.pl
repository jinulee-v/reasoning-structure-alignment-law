/* =========  Facts describing Robert's trip  ==================== */

/* price of the ticket */
flight_cost(570).

/* list of checked bags: bag(Id,Length,Width,Height,Weight).       */
/* (The personal-item backpack 18x13x8 - 7 lb is *not* listed.)    */
bag(2,37,15,12,51).
bag(3,38,22,15,51).
bag(4,38,14,11,66).
bag(5,36,22,12,59).
bag(6,37,18,10,56).
bag(7,36,16,13,51).
bag(8,37,16,11,51).
bag(9,43,25,23,63).
bag(10,38,13,13,60).
bag(11,43,27,23,65).

/* list (constant) of all checked-bag Ids                          */
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).

/* =========  Statutory rules for this itinerary  ================= */

/* sum of dimensions */
dims_sum(L,W,H,S) :- S is L+W+H.

/* ---------  Over-SIZE fees  (to / from Australia & NZ) ---------- */
oversize_fee(Sum,Fee) :-
       (   Sum =< 62      -> Fee = 0
       ;   Sum =< 65      -> Fee = 30
       ;   Sum =< 115     -> Fee = 200 ).

/* ---------  Over-WEIGHT fees  (to / from Australia & NZ) -------- */
/*  complimentary bags -> 70-lb limit ; charged bags -> 50-lb limit  */
overweight_fee(W,Limit,Fee) :-
       (   W =< Limit     -> Fee = 0
       ;   W =< 53        -> Fee = 30
       ;   W =< 70        -> Fee = 100
       ;   W =< 100       -> Fee = 200 ).

/* penalty for a bag: the HIGHER of over-size vs over-weight       */
penalty(BagId,comp,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,70,OW),        % complimentary -> 70-lb limit
       Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
       bag(BagId,L,W,H,Weight),
       dims_sum(L,W,H,Sum),
       oversize_fee(Sum,OS),
       overweight_fee(Weight,50,OW),        % charged -> 50-lb limit
       Pen is max(OS,OW).

/* ---------  Checked-bag BASE fees (Premium Economy) ------------- */
/* 1st & 2nd bags free; 3rd and onward $200 each                   */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(N,200) :- N >= 3.

/* =========  Helper predicates  ================================== */

/* choose two different elements (F1<F2) from a list               */
choose_two(List,F1,F2) :-
       append(_,[F1|Tail],List),
       member(F2,Tail).

/* create the ordered list: the 2 freebies go into positions 1 & 2 */
ordered_list(F1,F2,Ordered) :-
       checked_bag_ids(All),
       select(F1,All,R1),
       select(F2,R1,Rest),
       Ordered = [F1,F2|Rest].

/* cost for a particular choice of the 2 complimentary bags        */
cost_for_choice(F1,F2,Total) :-
       ordered_list(F1,F2,Ordered),
       cost_bags(Ordered,1,BaseFees,Penalties),
       flight_cost(Ticket),
       Total is Ticket + BaseFees + Penalties.

/* walk through list accumulating base fees and penalties          */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,BaseSum,PenSum) :-
       (Idx =< 2 -> Kind = comp ; Kind = charged),
       bag_fee(Idx,Fee),
       penalty(Bag,Kind,Pen),
       Next is Idx+1,
       cost_bags(Bs,Next,BaseRest,PenRest),
       BaseSum is Fee + BaseRest,
       PenSum  is Pen + PenRest.

/* overall minimal total across all ways of selecting 2 freebies   */
compute_total(MinTotal) :-
       checked_bag_ids(L),
       findall(T,
               ( choose_two(L,F1,F2),
                 cost_for_choice(F1,F2,T)),
               Totals),
       min_list(Totals,MinTotal).

/* =========  Query & output  ===================================== */
:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.