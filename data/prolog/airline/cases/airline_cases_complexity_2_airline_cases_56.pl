:- format("~w~n", ["Label: 2826"]).
/* =========================================================
   Mary - Business Class
   Boston (U.S.)  ->  Amsterdam (Europe)
   Goal: Compute total trip cost (ticket + all bag charges)
   ========================================================= */

/* -------- Ticket ---------------------------------------- */
flight_cost(186).


/* -------- Bags ------------------------------------------ */
/* bag(Id, Length, Width, Height, Weight).  (inches / pounds) */
bag(2,46,23,20,52).
bag(3,52,29,25,52).
bag(4,47,30,28,52).
bag(5,33,23, 9,51).
bag(6,36,18,11,68).
bag(7,45,30,23,69).
bag(8,38,11,14,57).
bag(9,35,17,11,59).
bag(10,34,15,14,57).
bag(11,50,33,25,51).

/* IDs of all checked pieces (carry-on item #1 is not listed) */
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).

/* -------- Statutory rules for this itinerary ------------- */

/* Sum of the 3 exterior dimensions */
dims_sum(L,W,H,S) :- S is L+W+H.

/* ---------- Oversize fees : Europe <-> U.S. -------------- */
/* 0-62 in  - $0   |  62-65 in - $30   |  65-115 in - $150   */
oversize_fee(S,0  ) :- S =< 62.
oversize_fee(S,30 ) :- S > 62,  S =< 65.
oversize_fee(S,150) :- S > 65,  S =< 115.

/* ---------- Overweight fees : Europe <-> U.S. ------------ */
/* Threshold depends on whether the bag itself is "free" or "charged".
   - complimentary bag : 70-lb allowance
   - charged bag       : 50-lb allowance                      */

overweight_fee(W,Thresh,Fee) :-
         ( W =< Thresh ->  Fee = 0
         ; W =< 53     ->  Fee = 30
         ; W =< 70     ->  Fee = 100   % >70 not accepted on this route
         ).

/* ---------- Penalty (oversize / overweight) -------------- */
/* The HIGHER of oversize vs overweight applies.             */

penalty(BagId,comp,Pen) :-                         /* complimentary bag */
         bag(BagId,L,W,H,Wt),
         dims_sum(L,W,H,S),
         oversize_fee(S,OS),
         overweight_fee(Wt,70,OW),
         Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-                      /* charged bag */
         bag(BagId,L,W,H,Wt),
         dims_sum(L,W,H,S),
         oversize_fee(S,OS),
         overweight_fee(Wt,50,OW),
         Pen is max(OS,OW).

/* ---------- Checked-bag base fees (Business Class) ------- */
/* 1st & 2nd checked bags free, all others $200 each          */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(N,200) :- N >= 3.

/* ---------- Helper predicates ---------------------------- */

/* choose 2 distinct elements (Ids) from a list */
choose_two(List,X,Y) :-
         append(_, [X|Tail], List),
         member(Y, Tail).

/* Remove freebies, build ordered list so that the           */
/* complimentary ones occupy positions 1 and 2               */
ordered_list(F1,F2,Ordered) :-
         checked_bag_ids(Base),
         select(F1,Base,R1),
         select(F2,R1,R2),
         Ordered = [F1,F2 | R2].

/* Cost for one specific choice of the two free bags */
cost_for_choice(F1,F2,Total) :-
         ordered_list(F1,F2,Seq),
         bags_cost(Seq,1,BagsCost,Penalties),
         flight_cost(Tix),
         Total is Tix + BagsCost + Penalties.

/* Walk through ordered list, accumulating base fees & penalties */
bags_cost([],_,0,0).
bags_cost([B|Bs],Idx,FeeSum,PenSum) :-
         (Idx =< 2 -> Type = comp ; Type = charged),
         bag_fee(Idx,BaseFee),
         penalty(B,Type,Pen),
         Next is Idx + 1,
         bags_cost(Bs,Next,FeeRest,PenRest),
         FeeSum is BaseFee + FeeRest,
         PenSum  is Pen + PenRest.

/* Compute minimal total over all ways of selecting 2 freebies */
total_cost(Min) :-
         checked_bag_ids(L),
         findall(T,
                 (choose_two(L,F1,F2),
                  cost_for_choice(F1,F2,T)),
                 Totals),
         min_list(Totals,Min).

/* -------------  Query &  Output  -------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.