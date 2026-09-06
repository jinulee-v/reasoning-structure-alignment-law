/* ---------------  Statutory rules that are relevant --------------- */

% ticket
ticket_price(282).

% passenger, trip and cabin facts (only what matters here)
region(within_us).
cabin(main_cabin).

% personal-item size limit (in inches)
personal_limit(18,14,8).

% carry-on limit - not needed because none of Joseph's items qualifies

/* ---------- base checked-bag fee for Main Cabin within U.S. -------- */
base_fee(Pos,Fee) :-
    Pos =:= 1 , Fee = 40  ;
    Pos =:= 2 , Fee = 45  ;
    Pos =:= 3 , Fee = 150 ;
    Pos  >  3 , Fee = 200.

/* --------------------- oversize fee (within U.S.) ------------------ */
oversize_fee(BagID,Fee) :-
    bag(BagID,L,W,H,_),
    S is L+W+H,
    (   S =< 62               -> Fee = 0
    ;   S =< 65               -> Fee = 30
    ;   S =< 115              -> Fee = 200
    ;   /* bigger than 115 - not accepted, but not the case here */   Fee = 0).

/* ------------------- overweight fee (within U.S.) ------------------ */
overweight_fee(BagID,Fee) :-
    bag(BagID,_,_,_,Wt),
    (   Wt =< 50              -> Fee = 0
    ;   Wt =< 53              -> Fee = 30
    ;   Wt =< 70              -> Fee = 100
    ;   Wt =< 100             -> Fee = 200
    ;   /* >100 - not accepted, not the case here */                  Fee = 0).

/* --------------- penalty fee: higher of over-size / weight --------- */
penalty_fee(BagID,Fee) :-
    oversize_fee(BagID,F1),
    overweight_fee(BagID,F2),
    (F1>=F2 -> Fee=F1 ; Fee=F2).

/* --------------- item facts for Joseph ----------------------------- */

% bag(Number,Length,Width,Height,Weight).
bag(1,18,14,7,11).      % personal item - will be free
bag(2,39,22,18,98).
bag(3,38,15,11,63).
bag(4,45,28,23,95).
bag(5,35,18,12,80).

/* -------------------- what is a personal item ---------------------- */
personal_item(BagID) :-
    personal_limit(PL,PW,PH),
    bag(BagID,L,W,H,_),
    L =< PL, W =< PW, H =< PH.

checked_bag(BagID) :-
    bag(BagID,_,_,_,_),
    \+ personal_item(BagID).

/* ---------------- cost of every checked bag ------------------------ */
checked_bag_cost(Pos,BagID,Cost) :-
    base_fee(Pos,Base),
    penalty_fee(BagID,Pen),
    Cost is Base + Pen.

/* ---------------- total cost of all checked bags ------------------- */
total_checked_bags_cost(Total) :-
    findall(BagID,checked_bag(BagID),BagIDs),
    assign_positions(BagIDs,1,Total).

assign_positions([],_,0).
assign_positions([BagID|Rest],Pos,Total) :-
    checked_bag_cost(Pos,BagID,C),
    Pos1 is Pos+1,
    assign_positions(Rest,Pos1,RestCost),
    Total is C + RestCost.

/* ----------------------- grand total ------------------------------- */
total_cost(Total) :-
    ticket_price(T),
    total_checked_bags_cost(BagCost),
    Total is T + BagCost.

/* --------------------- helper: run the query ----------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.