/* -------------  Statutory rules needed for this case ------------- */

/* Carry-on test (American allows 22 x 14 x 9 in.) */
carry_on(BagId) :-
    bag(BagId,L,W,H,_),
    L =< 22, W =< 14, H =< 9.

/* ----------  Domestic (U.S.-only) checked-bag base fees ---------- */
/* Premium-Economy customers: 1st & 2nd bag free, 3rd $150, 4th+ $200 */

base_checked_fee(Order,0)  :- Order =:= 1 ; Order =:= 2.
base_checked_fee(3,150).
base_checked_fee(Order,200) :- Order >= 4.

/* ---------------- Oversize fee (within / between U.S.) ----------- */
oversize_fee(L,W,H,Fee) :-
    Dim is L+W+H,
    ( Dim =< 62  -> Fee = 0
    ; Dim =< 65  -> Fee = 30          % 62 < dim =< 65
    ; Dim =< 115 -> Fee = 200         % 65 < dim =< 115
    ).

/* --------------- Over-weight fee (within / between U.S.) ---------- */
overweight_fee(Wt,Fee) :-
    ( Wt =< 50 -> Fee = 0
    ; Wt =< 53 -> Fee = 30            % 50 < wt =< 53
    ; Wt =< 70 -> Fee = 100           % 53 < wt =< 70
    ; Wt =< 100 -> Fee = 200          % 70 < wt =< 100
    ).

/* -------- Combined extra fee: higher of over-size / over-weight --- */
extra_fee(BagId,Fee) :-
    bag(BagId,L,W,H,Wt),
    oversize_fee(L,W,H,OSFee),
    overweight_fee(Wt,OWFee),
    Fee is max(OSFee,OWFee).

/* ------------------- Total fee for one checked bag ---------------- */
bag_fee(BagId,Order,Fee) :-
    base_checked_fee(Order,Base),
    extra_fee(BagId,Extra),
    Fee is Base + Extra.

/* ----------------------  Facts of the present case ---------------- */

ticket_price(141).            % flight price (USD)

bag(1,21,12,7,  9).           % BagId, L, W, H, Weight (lbs)
bag(2,43,28,23,51).
bag(3,41,24,21,97).
bag(4,33,20,12,52).
bag(5,45,27,17,96).
bag(6,51,25,26,82).
bag(7,33,19,11,53).
bag(8,38,15,10,79).

/* ---------------------  Aggregate all checked bags ---------------- */

checked_bag_list(Checked) :-
    findall(Id, (bag(Id,_,_,_,_), \+ carry_on(Id)), List),
    sort(List,Checked).        % keep numeric order

checked_bag_fees(Total) :-
    checked_bag_list(Bags),
    calc_fees(Bags,1,0,Total).

calc_fees([],_,Acc,Acc).
calc_fees([BagId|Rest],Order,Acc,Total) :-
    bag_fee(BagId,Order,Fee),
    Acc1 is Acc + Fee,
    Order1 is Order + 1,
    calc_fees(Rest,Order1,Acc1,Total).

/* ---------------------------  Grand total ------------------------- */
total_cost(Total) :-
    checked_bag_fees(BagFees),
    ticket_price(Ticket),
    Total is BagFees + Ticket.

/* ---------------------------  Query --------------------------------*/
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.