/* ----------  Rules from the statutes (restricted to this case) ---------- */

:- use_module(library(lists)).

/* item(Id,Length,Width,Height,Weight).  */
item(1,22,14, 6,  8).
item(2,40,18,15, 59).
item(3,35,21, 9, 51).
item(4,36,22,12, 72).
item(5,35,18,11, 86).
item(6,37,22,17, 64).
item(7,35,17,12, 51).
item(8,34,17,12, 67).

/* ----------------  Free carry-on allowance  ---------------- */

carry_on_item(1).            % exactly 1 bag fits the 22*14*9 in. limit

checked_item(Id) :-           % every other item will be checked
    item(Id,_,_,_,_),
    \+ carry_on_item(Id).

/* --------------  size / weight surcharges  ----------------- */

dimension_sum(Id,S) :-
    item(Id,L,W,H,_),
    S is L+W+H.

/* oversize fees (within U.S.) */
oversize_fee(Id,Fee) :-
    dimension_sum(Id,S),
    (   S > 65          -> Fee = 200         % over 65 in - 115 in
    ;   S > 62          -> Fee = 30          % over 62 in - 65 in
    ;                       Fee = 0).

/* overweight fees (within U.S.) */
overweight_fee(Id,Fee) :-
    item(Id,_,_,_,Wt),
    (   Wt >  70        -> Fee = 200         % 70-100 lb
    ;   Wt >  53        -> Fee = 100         % 53-70  lb
    ;   Wt >  50        -> Fee = 30          % 50-53  lb
    ;                       Fee = 0).

/* choose the higher of the two surcharges */
extra_fee(Id,Fee) :-
    oversize_fee(Id,O),
    overweight_fee(Id,W),
    (O >= W -> Fee = O ; Fee = W).

/* --------------  basic checked-bag fees (Basic Econ., domestic) ---------- */

bag_base_fee(Idx,Fee) :-      % Idx starts at 1 for the 1st checked bag
    (   Idx =:= 1 -> Fee = 40
    ;   Idx =:= 2 -> Fee = 45
    ;   Idx =:= 3 -> Fee = 150
    ;                 Fee = 200).

/* total base fees for all checked bags */
base_total(Total) :-
    findall(Id,checked_item(Id),Ids),
    length(Ids,N),
    base_total_acc(1,N,0,Total).

base_total_acc(I,N,Acc,Total) :-
    (   I > N
    ->  Total = Acc
    ;   bag_base_fee(I,FeeI),
        Acc1 is Acc + FeeI,
        I1 is I + 1,
        base_total_acc(I1,N,Acc1,Total)
    ).

/* total surcharges for all checked bags */
extra_total(Total) :-
    findall(F,(checked_item(Id),extra_fee(Id,F)),Fs),
    sum_list(Fs,Total).

/* -----------------------  grand total ----------------------- */

flight_ticket(47).

total_cost(Total) :-
    base_total(Base),
    extra_total(Extra),
    flight_ticket(Tix),
    Total is Base + Extra + Tix.

/* --------------------  produce the answer ------------------- */

:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.