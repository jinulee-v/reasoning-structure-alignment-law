/* -------------  Ticket information ------------- */
flight_cost(1325).

/* -------------  Carry-on (will not be priced) ------------- */
/* bag(1,21,11,8,5).   % carry-on - omitted from checked list */

/* -------------  Checked bags (Id,Length,Width,Height,Weight) ------------- */
bag(2,36,16,11,64).
bag(3,33,19,13,61).
bag(4,35,18,11,53).
bag(5,37,17,10,68).
bag(6,54,30,31,53).
bag(7,34,18,11,75).
bag(8,48,27,27,63).
bag(9,37,12,14,52).
bag(10,37,15,12,87).
bag(11,37,18,10,52).

/* list of all checked-bag Ids (for enumeration) */
checked_bag_ids([2,3,4,5,6,7,8,9,10,11]).

/* ------------------------------------------------------------- */
/* ---------- Statutory rules for China <-> U.S. route ----------- */
/* ------------------------------------------------------------- */

/* dimensional sum */
dims_sum(L,W,H,S) :- S is L+W+H.

/* oversize fee: China / Japan / Korea / HK / India / Aus / NZ table */
oversize_fee(Sum,Fee) :-
    ( Sum =< 62  -> Fee = 0
    ; Sum =< 65  -> Fee = 30
    ; Sum =< 115 -> Fee = 200).

/* overweight fee with variable free-allowance threshold          */
/* Thresh = 70 lbs for complimentary bags (1st & 2nd)             */
/* Thresh = 50 lbs for charged bags                               */
overweight_fee(W,Thresh,Fee) :-
    ( W =< Thresh -> Fee = 0
    ; W =< 53     -> Fee = 30
    ; W =< 70     -> Fee = 100
    ; W =< 100    -> Fee = 450).

/* penalty for a bag = higher of oversize vs overweight fee */
penalty(BagId,comp,Pen) :-
    bag(BagId,L,W,H,Weight),
    dims_sum(L,W,H,Sum),
    oversize_fee(Sum,OS),
    overweight_fee(Weight,70,OW),   % complimentary bag -> 70-lb allowance
    Pen is max(OS,OW).

penalty(BagId,charged,Pen) :-
    bag(BagId,L,W,H,Weight),
    dims_sum(L,W,H,Sum),
    oversize_fee(Sum,OS),
    overweight_fee(Weight,50,OW),   % charged bag -> 50-lb allowance
    Pen is max(OS,OW).

/* base checked-bag fee for Business Class on this route */
bag_fee(1,0).
bag_fee(2,0).
bag_fee(N,200) :- N >= 3.

/* ------------------------------------------------------------- */
/* ----------------------  Helpers  ---------------------------- */
/* ------------------------------------------------------------- */

/* choose 2 different elements (F1<F2) from a list */
choose_two(List,F1,F2) :-
    append(_, [F1|Tail], List),
    member(F2, Tail).

/* reorder list so freebies occupy positions 1 and 2 */
ordered_list(F1,F2,Ordered) :-
    checked_bag_ids(All),
    select(F1, All, R1),
    select(F2, R1, Rest),
    Ordered = [F1,F2|Rest].

/* cost for a particular ordering (given the 2 freebies) */
cost_for_choice(F1,F2,TotalCost) :-
    ordered_list(F1,F2,Ordered),
    cost_bags(Ordered,1,BagsCost,Penalties),
    flight_cost(Tix),
    TotalCost is Tix + BagsCost + Penalties.

/* iterate through ordered list accumulating fees / penalties */
cost_bags([],_,0,0).
cost_bags([Bag|Bs],Idx,CostSum,PenSum) :-
    (Idx =< 2 -> Type = comp ; Type = charged),
    bag_fee(Idx,BFee),
    penalty(Bag,Type,Pen),
    NextIdx is Idx + 1,
    cost_bags(Bs,NextIdx,RestCost,RestPen),
    CostSum is BFee + RestCost,
    PenSum  is Pen   + RestPen.

/* minimal total cost over all ways of selecting the 2 free bags */
compute_total(Min) :-
    checked_bag_ids(Ids),
    findall(T,
            ( choose_two(Ids,F1,F2),
              cost_for_choice(F1,F2,T)
            ),
            Totals),
    min_list(Totals,Min).

/* ------------------------------------------------------------- */
/* -------------------  Final answer  -------------------------- */
:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.