import {
  Column,
  CreateDateColumn,
  Entity,
  PrimaryGeneratedColumn,
  UpdateDateColumn,
} from 'typeorm';

@Entity('result', { schema: 'public' })
export class Result {
  @PrimaryGeneratedColumn({ type: 'integer', name: 'id' })
  id: number;

  @CreateDateColumn({
    type: 'timestamp with time zone',
    name: 'createdAt',
    default: () => 'CURRENT_TIMESTAMP',
  })
  createdAt: string;

  @UpdateDateColumn({
    type: 'timestamp with time zone',
    name: 'updatedAt',
    nullable: true,
  })
  updatedAt: string | null;

  @Column('varchar', { unique: true, name: 'name' })
  name: string;

  @Column('integer', { name: 'level' })
  level: number;

  @Column('integer', { name: 'craftingPrice' })
  craftingPrice: number;

  @Column('varchar', { name: 'basic' })
  basic: string;

  @Column('varchar', { name: 'counts' })
  counts: string;

  @Column('varchar', { name: 'prices' })
  prices: string;

  @Column('integer', { name: 'totalPrice' })
  totalPrice: number;
}
