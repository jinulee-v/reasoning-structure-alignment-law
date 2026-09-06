/* ---------- Facts (case data) ---------- */
ticket_cost(880).          /* price of the flight itself */

/* Each checked piece: bag(Id, Length, Width, Height, Weight).            */
/* (Carry-on item is omitted - it's free and doesn't affect the total.)   */
bag(bag2,38,21,18,60).
bag(bag3,47,32,24,57).
bag(bag4,39,19,18,96).
bag(bag5,38,14,12,100).
bag(bag6,34,17,14,54).
bag(bag7,44,23,17,52).
bag(bag8,37,26,13,91).

/* List of all checked bags */
bag_ids([bag2,bag3,bag4,bag5,bag6,bag7,bag8]).

/* ---------- Statutory rules (to / from China in Business class) ------- */

/* Oversize fee to / from China (US bound):
      0  if =< 62 in
     30  if 62 < size =< 65 in
    200  if 65 < size =< 115 in      */
oversize_fee(Size,0  ) :- Size =< 62, !.
oversize_fee(Size,30 ) :- Size =< 65, !.
oversize_fee(Size,200) :- Size =< 115, !.
oversize_fee(_,999999).                 /* Not accepted - huge value   */

/* Over-weight fee to / from China (Business):
   Limits differ for complimentary vs. excess-charge bags            */
overweight_fee(Weight,Limit,0 ) :- Weight =< Limit, !.
overweight_fee(Weight,_,30 )  :- Weight =< 53, !.   % >Limit (50/70)-53
overweight_fee(Weight,_,100)  :- Weight =< 70, !.
overweight_fee(Weight,_,450)  :- Weight =< 100, !.
overweight_fee(_,_,999999).                /* Not accepted            */

/* Cost for a single bag given whether it's 1 of the 2 complimentary ones */
bag_cost(IsFree,Bag,Cost) :-
    bag(Bag,L,W,H,Weight),
    Size is L+W+H,
    ( IsFree = true  -> CheckedFee = 0 , Limit = 70   % complimentary
    ; IsFree = false -> CheckedFee = 200, Limit = 50  % 3rd bag onward
    ),
    oversize_fee(Size,OSFee),
    overweight_fee(Weight,Limit,OWFee),
    ExtraFee is max(OSFee,OWFee),            % higher of the 2 applies
    Cost is CheckedFee + ExtraFee.

/* ---------- Choose the 2 complimentary bags so total cost is minimum -- */
select_two_free([A,B]) :-
    bag_ids(Bags),
    select(A,Bags,Rest),
    select(B,Rest,_),
    A @< B.                                  % avoid duplicate pairs

total_bag_cost(FreeList,Total) :-
    findall(Cost,
            ( bag_ids(Ids),
              member(Bag,Ids),
              ( member(Bag,FreeList) -> IsFree=true ; IsFree=false ),
              bag_cost(IsFree,Bag,Cost)
            ),
            Costs),
    sum_list(Costs,Total).

min_bag_cost(Min) :-
    findall(Total,
            ( select_two_free(Free),
              total_bag_cost(Free,Total)
            ),
            Totals),
    min_list(Totals,Min).

/* ---------- Overall charge -------------------------------------------- */
total_cost(Total) :-
    ticket_cost(Tix),
    min_bag_cost(Bags),
    Total is Tix + Bags.

/* ---------- Output ---------------------------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.