/* ---------- Statutory rules that apply to Patricia's trip --------- */

/* Oversize fees for travel to / from China (sizes are length+width+height) */
oversize_fee(Size, 0)      :- Size =< 62.
oversize_fee(Size, 30)     :- Size  > 62, Size =< 65.
oversize_fee(Size, 200)    :- Size  > 65, Size =< 115.

/* Over-weight fees for travel to / from China (Main Cabin) */
overweight_fee(Weight, 0)      :- Weight =< 50.
overweight_fee(Weight, 30)     :- Weight  > 50, Weight =< 53.
overweight_fee(Weight, 100)    :- Weight  > 53, Weight =< 70.
overweight_fee(Weight, 450)    :- Weight  > 70, Weight =< 100.

/* Choose the higher of the 2 surcharges, in addition to the checked-bag fee */
max_fee(A,B,A) :- A>=B, !.
max_fee(_,B,B).

surcharge(Weight,Size,Fee) :-
    oversize_fee(Size, O),
    overweight_fee(Weight,W),
    max_fee(O,W,Fee).

/* Base checked-bag fee number 1..N for Main Cabin passenger on China route */
base_checked_fee(1,0).
base_checked_fee(2,100).
base_checked_fee(N,200) :- N>=3.

/* ------------- Facts that describe Patricia's case ---------------- */

/* bag(ID, Length, Width, Height, Weight) */
bag(1,21,11, 9,  8).   % carry-on
bag(2,37,16,10, 51).
bag(3,45,21,21, 77).
bag(4,35,16,13, 80).
bag(5,40,19,18, 60).
bag(6,33,21,11, 93).
bag(7,38,12,14, 83).
bag(8,35,21,13, 52).
bag(9,34,20,11, 61).
bag(10,37,22,12,51).
bag(11,34,19,10,52).

/* Carry-on test */
carry_on(ID) :-
    bag(ID,L,W,H,_),
    L =< 22, W =< 14, H =< 9.

/* Checked bag if it is not the free carry-on */
checked_bag(ID) :- bag(ID,_,_,_,_), \+ carry_on(ID).

/* Helper: total size of a bag */
bag_size(ID,Size) :-
    bag(ID,L,W,H,_),
    Size is L+W+H.

/* Map original bag order to sequential checked-bag number.
   Since only bag 1 is carry-on, CheckedNo = ID-1. */
bag_number(ID,CheckedNo) :-
    CheckedNo is ID-1.

/* Charge for one checked bag */
bag_charge(ID,Charge) :-
    checked_bag(ID),
    bag(ID,_,_,_,Weight),
    bag_size(ID,Size),
    bag_number(ID,N),          % N = 1..10 here
    base_checked_fee(N,Base),
    surcharge(Weight,Size,S),
    Charge is Base + S.

/* Sum of all checked-bag charges */
total_bag_cost(Total) :-
    findall(C, bag_charge(_,C), Cs),
    sum_list(Cs,Total).

/* Ticket price */
ticket_price(1020).

/* ------------------- Final total Patricia pays -------------------- */
total_cost(Total) :-
    ticket_price(T),
    total_bag_cost(B),
    Total is T + B.

:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.