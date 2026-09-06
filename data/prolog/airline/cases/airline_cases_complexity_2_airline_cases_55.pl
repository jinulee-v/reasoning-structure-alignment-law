/* -------------  STATUTORY RULES ------------- */

/* Base checked-bag fee for a Basic Economy passenger on a
   flight within / between the U.S., Puerto Rico and the
   U.S. Virgin Islands                                       */
base_fee(1,40).        /* 1st checked bag  */
base_fee(2,45).        /* 2nd checked bag  */
base_fee(3,150).       /* 3rd checked bag  */
base_fee(N,200) :- N>=4.   /* 4th bag and beyond */

/* Over-weight fee (within U.S. - any cabin) */
overweight_fee(W,200) :- W>70.        /* > 70-100 lbs */
overweight_fee(W,100) :- W>53, W=<70. /* > 53-70 lbs  */
overweight_fee(W,30)  :- W>50, W=<53. /* > 50-53 lbs  */
overweight_fee(W,0)   :- W=<50.       /* up to 50 lbs */

/* Over-size fee (within U.S. / Canada) - linear inches */
oversize_fee(D,200) :- D>65.
oversize_fee(D,30)  :- D>62, D=<65.
oversize_fee(D,0)   :- D=<62.

/* The statute states that when both over-weight and over-size apply,
   only the HIGHER of the two is charged (in addition to the base fee) */
extra_fee(Weight,Dim,Extra) :-
    overweight_fee(Weight,OW),
    oversize_fee(Dim,OS),
    ( OW>=OS -> Extra=OW ; Extra=OS ).

/* -------------  CASE FACTS ------------- */

/* item(ID, Type, Length, Width, Height, Weight) */
item(1,backpack, 20,13,8,  9).
item(2,luggage_box,35,16,13,52).
item(3,backpack,   37,16,15,53).
item(4,backpack,   41,22,15,62).
item(5,backpack,   40,19,19,67).
item(6,luggage_box,38,13,13,70).
item(7,luggage_box,39,19,12,73).
item(8,backpack,   40,27,15,73).
item(9,luggage_box,35,19,13,51).
item(10,backpack,  39,16,11,88).
item(11,luggage_box,34,19,11,71).

/* Carry-on rules (1 personal + 1 carry-on allowed free)          */
/* A carry-on must be =< 22 x 14 x 9 inches                        */
carry_on(ItemID) :-
    item(ItemID,_,L,W,H,_),
    L=<22, W=<14, H=<9.

/* Checked items are those that are NOT free carry-ons            */
checked_item(ItemID) :-
    item(ItemID,_,_,_,_,_),
    \+ carry_on(ItemID).

/* -------------  FEE CALCULATIONS ------------- */

/* Linear dimension of a bag */
linear_dim(ID,Dim) :-
    item(ID,_,L,W,H,_),
    Dim is L+W+H.

/* Fee for one checked bag, given its order (Idx) in the list      */
bag_fee(ID,Idx,Fee) :-
    item(ID,_,_,_,_,Weight),
    linear_dim(ID,Dim),
    base_fee(Idx,Base),
    extra_fee(Weight,Dim,Extra),
    Fee is Base + Extra.

/* List all checked bags in ascending ID order                     */
checked_bag_list(List) :-
    findall(ID,checked_item(ID),BagIDs),
    sort(BagIDs,List).

/* Compute the total checked-bag cost                              */
total_checked_fee(Total) :-
    checked_bag_list(List),
    total_checked_fee(List,1,0,Total).

total_checked_fee([],_,Acc,Acc).
total_checked_fee([ID|Rest],Idx,Acc,Total) :-
    bag_fee(ID,Idx,F),
    Acc1 is Acc+F,
    Idx1 is Idx+1,
    total_checked_fee(Rest,Idx1,Acc1,Total).

/* Flight ticket price                                             */
ticket_price(108).

/* TOTAL COST = ticket + all bag fees                              */
total_cost(Total) :-
    ticket_price(T),
    total_checked_fee(BagFees),
    Total is T+BagFees.

/* -------------  QUERY ------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.