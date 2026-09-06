/* -------  Statutory rules that matter for this case  ------- */

/* flight facts */
flight_region(domestic).          /* Charlotte - Dallas */
cabin(main_cabin).                /* Main Cabin ticket   */
ticket_cost(265).                 /* Price of the ticket */

/* passenger's items: bag(ID,Length,Width,Height,Weight). */
bag(1,21,14,7,12).
bag(2,34,18,12,56).
bag(3,35,16,14,70).
bag(4,36,14,14,95).
bag(5,51,31,29,52).

/* ---------- helper predicates ---------- */
dimension_sum(L,W,H,S):- S is L+W+H.

personal_item(B):- bag(B,L,W,H,_), L=<18, W=<14, H=<8.
carry_on(B)    :- bag(B,L,W,H,_), L=<22, W=<14, H=<9, \+ personal_item(B).
checked(B)     :- bag(B,_,_,_,_), \+ personal_item(B), \+ carry_on(B).

/* ---------- base checked-bag fees (Main Cabin, domestic) ---------- */
base_fee(Index,Fee):-
    cabin(main_cabin),
    flight_region(domestic),
    domestic_maincabin_base(Index,Fee).

domestic_maincabin_base(1,40).
domestic_maincabin_base(2,45).
domestic_maincabin_base(3,150).
domestic_maincabin_base(N,200):- N>=4.

/* ---------- overweight fees (domestic) ---------- */
overweight_fee(W,30) :- W>50 , W=<53.
overweight_fee(W,100):- W>53 , W=<70.
overweight_fee(W,200):- W>70 , W=<100.

/* ---------- oversize fees (domestic) ---------- */
oversize_fee(L,W,H,30)  :- dimension_sum(L,W,H,S), S>62 , S=<65.
oversize_fee(L,W,H,200) :- dimension_sum(L,W,H,S), S>65 , S=<115.

/* choose the higher of the 2 surcharges (or 0 if none) */
extra_fee(BagID,Extra):-
    bag(BagID,L,W,H,Wt),
    (overweight_fee(Wt,OW) -> true ; OW=0),
    (oversize_fee(L,W,H,OS)-> true ; OS=0),
    Extra is max(OW,OS).

/* list of checked bags in the order they appear */
checked_bag_list(L):- findall(B,checked(B),L).

/* fee for each checked bag (base + extra) */
bag_total_fee(BagID,Idx,Fee):-
    base_fee(Idx,Base),
    extra_fee(BagID,Extra),
    Fee is Base+Extra.

/* sum of all checked-bag fees */
total_bag_fees(Total):-
    checked_bag_list(Bags),
    findall(F,
            (nth1(I,Bags,B), bag_total_fee(B,I,F)),
            Fs),
    sum_list(Fs,Total).

/* grand total = ticket + bags */
total_cost(Grand):-
    ticket_cost(T),
    total_bag_fees(BF),
    Grand is T+BF.

/* ----------- produce the answer ----------- */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.