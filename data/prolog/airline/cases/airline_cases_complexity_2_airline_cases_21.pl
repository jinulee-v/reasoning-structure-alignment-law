/* ---------- Facts ---------- */
/* bag(Id, Length, Width, Height, Weight). */
bag(1,19,12,7,5).
bag(2,44,22,22,52).
bag(3,50,27,28,53).
bag(4,46,30,25,93).
bag(5,48,30,25,51).
bag(6,38,14,12,69).
bag(7,39,20,14,55).
bag(8,36,16,11,97).
bag(9,48,31,28,83).
bag(10,38,16,10,59).
bag(11,44,26,22,55).

ticket_cost(34).

/* ---------- Carry-on rule (fits AA sizer 22x14x9) ---------- */
is_carry_on(ID) :-
    bag(ID,L,W,H,_),
    L =< 22, W =< 14, H =< 9.

/* ---------- Build checked-bag list ---------- */
checked_bags(Ids) :-
    findall(ID, (bag(ID,_,_,_,_), \+ is_carry_on(ID)), Ids).

/* ---------- Oversize fee (within / between U.S. & Canada) ---------- */
oversize_fee(ID,Fee) :-
    bag(ID,L,W,H,_),
    S is L+W+H,
    (  S =< 62  -> Fee = 0
    ;  S =< 65  -> Fee = 30
    ;  S =< 115 -> Fee = 200
    ;  Fee = 999999  /* not accepted - not needed here */ ).

/* ---------- Overweight fee (within / between U.S. & Canada) ---------- */
overweight_fee(ID,Fee) :-
    bag(ID,_,_,_,Wt),
    (  Wt =< 50  -> Fee = 0
    ;  Wt =< 53  -> Fee = 30
    ;  Wt =< 70  -> Fee = 100
    ;  Wt =< 100 -> Fee = 200
    ;  Fee = 999999 ).

/* ---------- Additional fee = higher of the two ---------- */
additional_fee(ID,Fee) :-
    oversize_fee(ID,O),
    overweight_fee(ID,W),
    (O >= W -> Fee = O ; Fee = W).

/* ---------- Base checked-bag fee for Main Cabin within U.S. ---------- */
base_fee(Pos,Fee) :-
    ( Pos =:= 1 -> Fee = 40
    ; Pos =:= 2 -> Fee = 45
    ; Pos =:= 3 -> Fee = 150
    ; Pos  >= 4 -> Fee = 200 ).

/* ---------- Aggregate checked-bag charges ---------- */
bag_fees(Total) :-
    checked_bags(Ids),
    bag_fees(Ids,1,Total).

bag_fees([],_,0).
bag_fees([ID|Rest],Pos,Total) :-
    base_fee(Pos,B),
    additional_fee(ID,A),
    Pos1 is Pos + 1,
    bag_fees(Rest,Pos1,RestTotal),
    Total is B + A + RestTotal.

/* ---------- Final total cost ---------- */
total_cost(Total) :-
    ticket_cost(T),
    bag_fees(Bags),
    Total is T + Bags.

/* ---------- Query & output ---------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.