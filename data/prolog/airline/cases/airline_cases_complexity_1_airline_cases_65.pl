/* ---------- Facts describing the passenger, flight and bags ---------- */
flight_region(within_us).            /* Seattle - Salt Lake City          */
passenger_class(premium_economy).    /* Premium Economy                   */
ticket_price(102).                   /* Flight ticket                     */

% bag(Id, Length, Width, Height, Weight).
bag(1,21,11, 8,  9).   /* free carry-on                               */
bag(2,37,16,10, 63).
bag(3,38,15,10, 64).
bag(4,48,27,25, 66).
bag(5,37,16,11, 53).
bag(6,34,21,10, 61).
bag(7,36,15,14, 53).
bag(8,37,20,12, 83).

/* ---------- Helper predicates ---------- */

% a single free carry-on is allowed if it fits the sizer (22*14*9 in.)
carry_on(BagId) :-
    bag(BagId,L,W,H,_),
    L =< 22, W =< 14, H =< 9.

% Per-bag oversize fee for the within-US region
oversize_fee(BagId,Fee) :-
    bag(BagId,L,W,H,_),
    Dim is L+W+H,
    ( Dim =< 62 -> Fee=0
    ; Dim =< 65 -> Fee=30
    ; Dim =<115 -> Fee=200
    ;               Fee=999999   % not accepted (won't occur here)
    ).

% Per-bag overweight fee for the within-US region
overweight_fee(BagId,Fee) :-
    bag(BagId,_,_,_,Wt),
    ( Wt =< 50 -> Fee=0
    ; Wt =< 53 -> Fee=30
    ; Wt =< 70 -> Fee=100
    ; Wt =<100 -> Fee=200
    ;              Fee=999999    % not accepted (won't occur here)
    ).

% The additional fee is the higher of oversize/overweight (policy text)
additional_fee(BagId,Fee) :-
    oversize_fee(BagId,OFee),
    overweight_fee(BagId,WFee),
    ( OFee >= WFee -> Fee=OFee ; Fee=WFee ).

/* Base checked-bag fees for Premium Economy within the U.S. */
base_fee(Order,Fee) :-
    ( Order =:= 1 -> Fee = 0
    ; Order =:= 2 -> Fee = 0
    ; Order =:= 3 -> Fee = 150
    ; Order  >= 4 -> Fee = 200).

/* ---------- Aggregate bag-fee calculation ---------- */
checked_bag_ids(List) :-
    findall(B, (bag(B,_,_,_,_), \+ carry_on(B)), List).

bags_total_fee(Total) :-
    checked_bag_ids(Bags),
    sort(Bags,Ordered),         % keep ascending order of IDs
    bags_total_fee(Ordered,1,0,Total).

bags_total_fee([],_,Acc,Acc).
bags_total_fee([B|Rest],Order,Acc,Total) :-
    base_fee(Order,Base),
    additional_fee(B,Add),
    Cost is Base + Add,
    Acc1 is Acc + Cost,
    Order1 is Order + 1,
    bags_total_fee(Rest,Order1,Acc1,Total).

/* ---------- Grand total (ticket + bags) ---------- */
total_cost(GrandTotal) :-
    ticket_price(Tix),
    bags_total_fee(BagFees),
    GrandTotal is Tix + BagFees.

/* ---------- Query requested by the grader ---------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.